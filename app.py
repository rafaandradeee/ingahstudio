import streamlit as st
import sys
import os
import zipfile
from io import BytesIO
import time
import stripe

# Adiciona o diretório raiz ao path para encontrar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from agents import equipe
from config import CONFIG
import google.genai as genai

# Importa o nosso novo gerente de banco de dados
from database import supabase, get_user_wallet, descontar_creditos

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Ingah AI Studio - SaaS",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- CONFIGURAÇÃO DO STRIPE ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

# --- REGRAS DE NEGÓCIO E FATURAMENTO ---
REGRA_PLANOS = {
    'F': {'nome': 'Free', 'creditos_base': 60, 'max_slides': 3, 'premium': False},
    'P': {'nome': 'Padrão', 'creditos_base': 300, 'max_slides': 10, 'premium': True},
    'U': {'nome': 'Ultimate', 'creditos_base': 1600, 'max_slides': 20, 'premium': True},
    'E': {'nome': 'Enterprise', 'creditos_base': 5000, 'max_slides': 20, 'premium': True}
}

# --- INICIALIZAÇÃO DA SESSÃO ---
if 'user' not in st.session_state:
    st.session_state.user = None
if 'client' not in st.session_state:
    try:
        st.session_state.client = genai.Client()
    except Exception:
        st.session_state.client = None

keys_to_init = {'tema_input': "", 'carrossel_dados': None, 'processando': False, 'cancelar_processo': False, 'slides_aprovados': {}}
for key, default_value in keys_to_init.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

def hex_to_rgba(hex_code, alpha=255):
    hex_code = hex_code.lstrip('#')
    if len(hex_code) != 6:
        return (255, 255, 255, alpha)
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

# --- FUNÇÕES DE PAGAMENTO (STRIPE) ---
def iniciar_checkout_stripe(user_id, email_usuario):
    """Gera uma sessão de checkout no Stripe para compra de créditos avulsos."""
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=email_usuario,
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'brl',
                    'product_data': {
                        'name': 'Pacote de 100 Créditos Extras - Ingah Studio',
                    },
                    'unit_amount': 2990, # Valor em centavos (R$ 29,90)
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://seu-app.streamlit.app/?pagamento=sucesso', # Altere para o seu link de produção futuramente
            cancel_url='https://seu-app.streamlit.app/?pagamento=cancelado',
            metadata={
                'user_id': user_id,
                'creditos_comprados': '100'
            }
        )
        return checkout_session.url
    except Exception as e:
        print(f"Erro ao criar sessão Stripe: {e}")
        return None


# --- FUNÇÕES DE CALLBACK DE EDIÇÃO ---
def reaplicar_texto_callback(slide_index):
    slide = st.session_state.carrossel_dados['roteiro_carrossel'][slide_index]
    slide['titulo'] = st.session_state[f"input_tit_{slide_index}"]
    slide['texto'] = st.session_state[f"input_tex_{slide_index}"]
    slide['texto_slide'] = slide['texto']
    
    slide['mostrar_titulo'] = st.session_state.get(f"chk_tit_{slide_index}", True)
    slide['mostrar_texto'] = st.session_state.get(f"chk_tex_{slide_index}", True)
    slide['mostrar_fundo'] = st.session_state.get(f"chk_fnd_{slide_index}", True)

    with st.spinner("⚡ Rediagramando arte..."):
        slide_atualizado = equipe.aplicar_tipografia_slide(slide, st.session_state.config_user)
        st.session_state.carrossel_dados['roteiro_carrossel'][slide_index] = slide_atualizado
    
    st.toast("⚡ Arte rediagramada!")
    time.sleep(0.5) 
    st.rerun()

def regerar_imagem_callback(slide_index):
    # 1. TENTA COBRAR PRIMEIRO (CUSTO DE 1 IMAGEM + 100% MARGEM)
    user_id = st.session_state.user.id
    custo_regeracao = 20 
    
    sucesso, msg = descontar_creditos(user_id, custo_regeracao)
    
    if not sucesso:
        st.toast(f"🚨 Saldo insuficiente para regerar a arte (Custa {custo_regeracao} Créditos).", icon="❌")
        return # Interrompe a função aqui e não gasta sua API do Google!

    # 2. SE COBROU, EXECUTA A IA
    slide = st.session_state.carrossel_dados['roteiro_carrossel'][slide_index]
    slide['titulo'] = st.session_state[f"input_tit_{slide_index}"]
    slide['texto'] = st.session_state[f"input_tex_{slide_index}"]
    slide['texto_slide'] = slide['texto']
    slide['instrucao_imagem'] = st.session_state.get(f"input_img_{slide_index}", "").strip()
    
    slide['mostrar_titulo'] = st.session_state.get(f"chk_tit_{slide_index}", True)
    slide['mostrar_texto'] = st.session_state.get(f"chk_tex_{slide_index}", True)
    slide['mostrar_fundo'] = st.session_state.get(f"chk_fnd_{slide_index}", True)

    with st.spinner(f"☁️ Regerando Slide {slide_index + 1} (-20 Créditos)..."):
        slide_atualizado = equipe.regerar_slide_individual(slide, slide_index, st.session_state.config_user)
        st.session_state.carrossel_dados['roteiro_carrossel'][slide_index] = slide_atualizado
    
    st.toast(f"Slide recriado com sucesso!", icon="✅")
    time.sleep(0.5)
    st.rerun()

def cancelar_esteira():
    st.session_state.processando = False
    st.session_state.cancelar_processo = True
    st.toast("🛑 Produção cancelada pelo usuário.")

# ==========================================================
# ROTA 1: TELA DE LOGIN E CADASTRO
# ==========================================================
if st.session_state.user is None:
    st.markdown("<br><br><h1 style='text-align: center;'>🍄 Ingah Studio</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>O seu esquadrão de IA para criação de carrosséis.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        tab_login, tab_cadastro = st.tabs(["🔐 Entrar", "✨ Criar Conta Grátis"])
        
        # --- TAB DE LOGIN ---
        with tab_login:
            with st.form("form_login"):
                email_login = st.text_input("E-mail")
                senha_login = st.text_input("Senha", type="password")
                btn_login = st.form_submit_button("Entrar no Estúdio", use_container_width=True)
                
                if btn_login:
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email_login, "password": senha_login})
                        st.session_state.user = res.user
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
                        
        # --- TAB DE CADASTRO ---
        with tab_cadastro:
            with st.form("form_cadastro"):
                email_cad = st.text_input("Seu melhor E-mail")
                senha_cad = st.text_input("Crie uma Senha (mín. 6 caracteres)", type="password")
                btn_cad = st.form_submit_button("Criar Conta e Ganhar 60 Créditos", use_container_width=True)
                
                if btn_cad:
                    try:
                        # 1. Cria a conta no Supabase Auth
                        res = supabase.auth.sign_up({"email": email_cad, "password": senha_cad})
                        
                        if res.user:
                            user_id = res.user.id

                            # IMPORTANTE: Faz o login automático na sessão para injetar o token de segurança
                            session_res = supabase.auth.sign_in_with_password({"email": email_cad, "password": senha_cad})
                            
                            # 2. Constrói a arquitetura do usuário no Banco de Dados
                            supabase.table('user_profiles').insert({"id": user_id, "email": email_cad, "plano_atual": "F"}).execute()
                            supabase.table('wallets').insert({"user_id": user_id, "creditos_plano": 60}).execute()
                            supabase.table('user_settings').insert({"user_id": user_id}).execute()

                            st.session_state.user = session_res.user
                            st.success("🎉 Conta criada com sucesso! Você já pode fazer o Login.")
                            st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao criar conta: {e}")

# ==========================================================
# ROTA 2: ESTÚDIO PRINCIPAL (USUÁRIO LOGADO)
# ==========================================================
else:
    # 1. Busca os dados reais do banco
    user_id = st.session_state.user.id
    email_usuario = getattr(st.session_state.user, 'email', '') or st.session_state.user.user_metadata.get('email', '')
    try:
        perfil = supabase.table('user_profiles').select('*').eq('id', user_id).execute().data[0]
    except:
        perfil = {'plano_atual': 'F', 'email': email_usuario}
        
    carteira = get_user_wallet(user_id) or {'creditos_plano': 0, 'creditos_avulsos': 0}
    
    plano_atual = perfil.get('plano_atual', 'F')
    plano = REGRA_PLANOS[plano_atual]
    is_free = not plano['premium']
    
    creditos_totais = carteira.get('creditos_plano', 0) + carteira.get('creditos_avulsos', 0)

    if 'config_user' not in st.session_state or not st.session_state.config_user:
        st.session_state.config_user = {
            'modelo_design': 'Padrão (Caixa Flutuante)',
            'formato_imagem': '1080 x 1080 px (Quadrado)',
            'marca_nome': 'EstudioIA',
            'qtd_slides': 3,
            'tom_de_voz': 'Viral & Clickbait',
            'fonte_familia': 'Poppins',
            'tam_capa': 58,
            'tam_titulo': 44,
            'tam_texto': 32,
            'cor_capa_rgba': hex_to_rgba('#FFFFFF'),
            'cor_texto_rgba': hex_to_rgba('#FFFFFF'),
            'opacidade_fundo': 190,
        }

    def pesquisar_tendencia():
        if st.session_state.client:
            with st.spinner("Buscando tendências..."):
                novo_tema = equipe.gerar_tema_autonomo(st.session_state.client)
                st.session_state.tema_input = novo_tema
                st.toast("💡 Nova tendência carregada!")

    def iniciar_esteira_com_cobranca():
        custo = 30 + (10 * st.session_state.config_user['qtd_slides'])
        
        if not st.session_state.tema_input.strip():
            st.warning("Por favor, forneça um tema ou pesquise uma tendência.")
            return

        # CHAMA O GERENTE FINANCEIRO NO BANCO DE DADOS
        sucesso, msg = descontar_creditos(user_id, custo)
        
        if sucesso:
            st.session_state.processando = True
            st.session_state.cancelar_processo = False
            st.session_state.carrossel_dados = None
        else:
            st.error(f"🚨 {msg} Faça um Upgrade ou compre créditos avulsos.")

    def fazer_logout():
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.carrossel_dados = None
        st.rerun()

    # --- UI: TOP BAR COM BOTÃO DE COMPRA DE CRÉDITOS ---
    col_topo_1, col_topo_2, col_topo_3 = st.columns([3, 2, 1])
    
    with col_topo_1:
        st.markdown("<div style='font-size: 1.4em; font-weight: 700; padding-top: 5px;'>🎨 Ingah Studio</div>", unsafe_allow_html=True)
    
    with col_topo_2:
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding-top: 5px;">
            <span style="background-color: #4CAF50; color: white; padding: 6px 12px; border-radius: 15px; font-weight: 600;">🪙 {creditos_totais} Créditos</span>
            <span style="background-color: rgba(255,255,255,0.1); padding: 6px 12px; border-radius: 15px;">👤 {plano['nome']}</span>
        </div>
        """, unsafe_allow_html=True)
        
    with col_topo_3:
        # Botão que redireciona para o checkout do Stripe ao clicar
        if st.button("⚡ + Créditos", use_container_width=True, type="primary"):
            url_checkout = iniciar_checkout_stripe(user_id, email_usuario)
            if url_checkout:
                st.markdown(f'<meta http-equiv="refresh" content="0;url={url_checkout}">', unsafe_allow_html=True)
                st.success("Redirecionando para o ambiente seguro de pagamento...")
            else:
                st.error("Erro ao gerar link de pagamento.")

    st.markdown("<hr style='margin-top: 0px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    st.button("Sair da Conta", on_click=fazer_logout, type="secondary")

    # --- UI: ÁREA DE PAUTA E CONFIGURAÇÕES ---
    if not st.session_state.processando:
        st.text_area("✍️ O que vamos criar hoje? (Digite um tema ou cole uma URL):", key='tema_input', height=100)
        st.button("🎲 Pesquisar Tendência (IA)", on_click=pesquisar_tendencia)

        with st.expander("⚙️ Configurações Visuais e Estrutura", expanded=False):
            if is_free:
                st.info("🔒 **Você está no plano Free.** Atualize seu plano para desbloquear personalizações de design, tamanhos e remover a marca d'água!")
                
            c1, c2, c3 = st.columns(3)
            with c1:
                st.session_state.config_user['modelo_design'] = st.selectbox("Modelo Visual", ["Padrão (Caixa Flutuante)", "Minimalista (Em breve)"], index=0, disabled=is_free)
                
                opcoes_formato = ["1080 x 1080 px (Quadrado)"]
                if plano_atual in ['U', 'E']:
                    opcoes_formato.append("1080 x 1440 px (Retrato)")
                else:
                    opcoes_formato.append("1080 x 1440 px 🔒 (Ultimate/Enterprise)")
                    
                if 'select_formato' not in st.session_state or st.session_state.select_formato not in opcoes_formato:
                    st.session_state.select_formato = opcoes_formato[0]
                    
                st.selectbox("Formato da Imagem", opcoes_formato, key="select_formato", disabled=is_free)
                st.session_state.config_user['formato_imagem'] = st.session_state.select_formato
                
                if 'slider_qtd' not in st.session_state:
                    st.session_state.slider_qtd = min(plano['max_slides'], st.session_state.config_user.get('qtd_slides', 3))
                    
                st.slider("Qtd de Slides (Máx 20)", 1, 20, key="slider_qtd")
                st.session_state.config_user['qtd_slides'] = st.session_state.slider_qtd

            with c2:
                st.session_state.config_user['tom_de_voz'] = st.selectbox("Tom de Voz", ["Viral & Clickbait", "Científico", "Tutorial", "Humor"], index=0, disabled=is_free)
                st.session_state.config_user['fonte_familia'] = st.selectbox("Fonte", ["Poppins"], index=0, disabled=is_free)
                val_marca = "Gerado por @EstudioIA" if is_free else st.session_state.config_user.get('marca_nome', 'EstudioIA')
                st.session_state.config_user['marca_nome'] = st.text_input("Seu @", value=val_marca, disabled=is_free)
                
            with c3:
                st.session_state.config_user['tam_capa'] = st.number_input("Tamanho Capa", value=st.session_state.config_user.get('tam_capa', 58), disabled=is_free)
                cor_capa = st.color_picker("Cor Título", "#FFFFFF", disabled=is_free)
                cor_texto = st.color_picker("Cor Texto", "#FFFFFF", disabled=is_free)
                cor_fundo = st.color_picker("Cor Fundo (Box)", "#000000", disabled=is_free) # NOVO CONTROLE DE COR
                
                st.session_state.config_user['cor_capa_rgba'] = hex_to_rgba(cor_capa)
                st.session_state.config_user['cor_texto_rgba'] = hex_to_rgba(cor_texto)
                
                # Aplica a opacidade na cor escolhida para o fundo
                opacidade_atual = st.session_state.config_user.get('opacidade_fundo', 190)
                st.session_state.config_user['cor_fundo_rgba'] = hex_to_rgba(cor_fundo, opacidade_atual)

        # Travas de segurança back-end
        if is_free:
            st.session_state.config_user['marca_nome'] = "Gerado por @EstudioIA"
            st.session_state.config_user['formato_imagem'] = "1080 x 1080 px (Quadrado)"
        if st.session_state.config_user.get('qtd_slides', 3) > plano['max_slides']:
            st.session_state.config_user['qtd_slides'] = plano['max_slides']

        custo_creditos_operacao = 30 + (10 * st.session_state.config_user['qtd_slides'])
        st.markdown("<br>", unsafe_allow_html=True)
        st.button(f"🚀 INICIAR ESTEIRA DE PRODUÇÃO (Custa {custo_creditos_operacao} Créditos)", type="primary", on_click=iniciar_esteira_com_cobranca, width='stretch')

    # --- UI: PROCESSAMENTO (ESTEIRA) E ESTÚDIO FICAM AQUI ---
    if st.session_state.processando:
        st.button("🛑 CANCELAR GERAÇÃO", type="secondary", on_click=cancelar_esteira, width='stretch')
        if not st.session_state.cancelar_processo:
            with st.status("🤖 O Esquadrão IA está em ação...", expanded=True) as status:
                briefing = equipe.run_agent_1(st.session_state.tema_input, st.session_state.client, CONFIG['gemini_model'], st.session_state.config_user)
                status.write("✍️ Agente 1: Briefing criado.")
                
                if briefing and not st.session_state.cancelar_processo:
                    draft = equipe.run_agent_2(briefing, st.session_state.client, CONFIG['gemini_model'], st.session_state.config_user)
                    status.write("✍️ Agente 2: Roteiro criado.")

                    if draft and not st.session_state.cancelar_processo:
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        output_dir = os.path.join("imagens_carrossel", timestamp)
                        os.makedirs(output_dir, exist_ok=True)

                        draft_com_imagens = equipe.run_agent_3_image_creator(draft, status, output_dir, st.session_state.config_user)
                        status.write("🎨 Agente 3: Imagens renderizadas e croppadas.")

                        if draft_com_imagens and not st.session_state.cancelar_processo:
                            status.write("🕵️ Agente 5: Revisando e lapidando os textos...")
                            draft_revisado = equipe.run_agent_5_reviewer(draft_com_imagens, st.session_state.client, CONFIG['gemini_model'], st.session_state.config_user)

                            if draft_revisado and not st.session_state.cancelar_processo:
                                status.write("✍️ Agente 4: Aplicando tipografia sobre o texto final aprovado...")
                                resultado_final = equipe.run_agent_4_typographer(draft_revisado, status, st.session_state.config_user)
                                
                                st.session_state.carrossel_dados = resultado_final
                                status.update(label="✅ Esteira finalizada com sucesso!", state="complete", expanded=False)

            st.session_state.processando = False
            st.rerun()

    # --- UI: ESTÚDIO DE APROVAÇÃO ---
    if st.session_state.carrossel_dados and not st.session_state.processando:
        st.markdown("---")
        st.header("🖼️ Estúdio de Aprovação e Retoque")

        slides = st.session_state.carrossel_dados.get('roteiro_carrossel', [])
        
        for i, slide in enumerate(slides):
            with st.container(border=True):
                col1, col2 = st.columns([1, 1])
                with col1:
                    caminho_img = slide.get('arquivo_imagem_local', '')
                    motivo_falha = slide.get('motivo_erro', 'Erro na geração.')

                    if caminho_img and os.path.exists(caminho_img):
                        st.image(caminho_img, width='stretch')
                    else:
                        st.error(f"🚨 Motivo Técnico: `{motivo_falha}`")
                with col2:
                    slide_num = slide.get('slide_numero', i + 1)
                    st.text_input(f"📌 Título (Slide {slide_num})", value=slide.get('titulo', ''), key=f"input_tit_{i}")
                    st.text_area(f"📝 Texto (Slide {slide_num})", value=slide.get('texto', ''), height=110, key=f"input_tex_{i}")
                    st.text_input(f"🎨 Instrução visual para IA (Opcional)", placeholder="Ex: Fundo escuro...", key=f"input_img_{i}")
                    
                    def_tit = slide.get('mostrar_titulo', True)
                    def_tex = slide.get('mostrar_texto', False if slide_num == 1 else True)
                    def_fnd = slide.get('mostrar_fundo', False if slide_num == 1 else True)
                    
                    t1, t2, t3 = st.columns(3)
                    with t1: st.checkbox("👁️ Título", value=def_tit, key=f"chk_tit_{i}")
                    with t2: st.checkbox("👁️ Texto", value=def_tex, key=f"chk_tex_{i}")
                    with t3: st.checkbox("⬛ Fundo", value=def_fnd, key=f"chk_fnd_{i}")
                    
                    st.checkbox("✅ Aprovar slide", key=f"aprovado_{i}", value=st.session_state.slides_aprovados.get(i, True))
                    
                    b1, b2 = st.columns(2)
                    with b1:
                        st.button("✍️ Reaplicar Texto", key=f"btn_reapply_{i}", on_click=reaplicar_texto_callback, args=(i,), width='stretch')
                    with b2:
                        st.button("🔄 Regerar Arte (20 Créditos)", key=f"btn_redo_{i}", on_click=regerar_imagem_callback, args=(i,), width='stretch')

        st.subheader("📦 Exportar")
        slides_finais = [s for i, s in enumerate(slides) if st.session_state.slides_aprovados.get(i, True)]
        
        if slides_finais:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zf:
                for s in slides_finais:
                    img_path = s.get('arquivo_imagem_local')
                    if img_path and os.path.exists(img_path):
                        zf.write(img_path, os.path.basename(img_path))
                zf.writestr("legenda.txt", st.session_state.carrossel_dados.get('legenda_instagram', ''))
                
            st.download_button("📦 BAIXAR PACOTE COMPLETO", data=zip_buffer.getvalue(), file_name=f"post_{time.strftime('%Y%m%d_%H%M')}.zip", mime="application/zip", width='stretch')
