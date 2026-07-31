"""
Módulo da Equipe de IA.

Define as funções para cada agente da equipe, incluindo a regeração individual
e a aplicação de configurações de usuário dinâmicas, com rastreamento de tokens e custos (USD).
"""
import re
import json
import os
import sys
import textwrap
import time
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from typing import Any, Dict, List
from google import genai
from urllib.parse import quote
from agents import prompts
from google.genai import types
from dotenv import load_dotenv
import random
import streamlit as st

def decodificar_json_seguro(texto: str) -> dict:
    texto_limpo = texto.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(texto_limpo)
    except json.JSONDecodeError:
        pass
    try:
        inicio = texto_limpo.find('{')
        fim = texto_limpo.rfind('}')
        if inicio != -1 and fim != -1 and fim > inicio:
            json_str = texto_limpo[inicio:fim+1]
            return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON aninhado: {e}. Tentando raw_decode.")
        try:
            resultado, _ = json.JSONDecoder().raw_decode(json_str)
            return resultado
        except (json.JSONDecodeError, NameError) as final_e:
            raise json.JSONDecodeError("Não foi possível decodificar o JSON após múltiplas tentativas.", texto, 0) from final_e
    raise json.JSONDecodeError("Não foi possível encontrar um objeto JSON válido no texto.", texto, 0)

def limpar_e_decodificar_json(texto_raw: str) -> dict:
    if not texto_raw:
        raise ValueError("O texto retornado pela API está vazio.")
    texto_limpo = texto_raw.replace("\xa0", " ").replace("\\u00a0", " ")
    texto_limpo = re.sub(r"^```(?:json)?\s*", "", texto_limpo.strip(), flags=re.IGNORECASE)
    texto_limpo = re.sub(r"\s*```$", "", texto_limpo.strip())
    match = re.search(r"\{.*\}", texto_limpo, re.DOTALL)
    if match:
        texto_limpo = match.group(0)
    try:
        return json.loads(texto_limpo)
    except json.JSONDecodeError as e:
        print(f"❌ Erro crítico ao decodificar JSON limpo: {e}")
        raise e

def gerar_tema_autonomo(client: Any) -> str:
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompts.PROMPT_GERADOR_TEMA
        )
        return response.text.strip().replace('"', '')
    except Exception as e:
        return f"Erro ao gerar tema: {e}"

def desenhar_texto_com_sombra(draw, pos, texto, fonte, fill, shadow_color=(0,0,0,200), offset=(2, 2), spacing=8, stroke_width=0, stroke_fill=None, align="center"):
    x, y = pos
    if stroke_width > 0:
        draw.text((x + offset[0], y + offset[1]), texto, font=fonte, fill=shadow_color, spacing=spacing, align=align, stroke_width=stroke_width, stroke_fill=shadow_color)
        draw.text((x, y), texto, font=fonte, fill=fill, spacing=spacing, align=align, stroke_width=stroke_width, stroke_fill=stroke_fill)
    else:
        draw.text((x + offset[0], y + offset[1]), texto, font=fonte, fill=shadow_color, spacing=spacing, align=align)
        draw.text((x, y), texto, font=fonte, fill=fill, spacing=spacing, align=align)

def get_font_path(font_family, weight='SemiBold'):
    diretorio_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pasta_fontes = os.path.join(diretorio_raiz, 'fonts')
    font_map = {
        'Poppins': {
            'SemiBold': os.path.join(pasta_fontes, 'Poppins-SemiBold.ttf'),
            'Medium': os.path.join(pasta_fontes, 'Poppins-Medium.ttf')
        }
    }
    if font_family not in font_map:
        if weight == 'SemiBold':
            return "C:/Windows/Fonts/segoeuib.ttf"
        return "C:/Windows/Fonts/segoeui.ttf"
    return font_map.get(font_family, {}).get(weight, font_map['Poppins'][weight])

def aplicar_tipografia_slide(slide_dict: dict, config_user: dict = None) -> dict:
    if config_user is None:
        config_user = {}

    slide_num = slide_dict.get('slide_numero') or slide_dict.get('index', 0) + 1
    total_slides = config_user.get('qtd_slides', 6)
    modelo_design = config_user.get('modelo_design', 'Padrão (Caixa Flutuante)')
    
    titulo_raw = slide_dict.get('titulo') or ''
    texto_raw = slide_dict.get('texto') or slide_dict.get('texto_slide') or ''
    
    # Visibilidade padrão (Capa começa sem texto e sem fundo, slides começam com tudo ativado)
    mostrar_titulo = slide_dict.get('mostrar_titulo', True)
    mostrar_texto = slide_dict.get('mostrar_texto', False if slide_num == 1 else True)
    mostrar_fundo = slide_dict.get('mostrar_fundo', False if slide_num == 1 else True)
    
    if not titulo_raw.strip() and texto_raw.strip():
        linhas = [l.strip() for l in texto_raw.split('\n') if l.strip()]
        if len(linhas) > 0:
            if ". " in linhas[0] and len(linhas[0].split(". ")[0]) <= 60:
                partes = linhas[0].split(". ", 1)
                titulo_raw = partes[0]
                texto_restante_linha = partes[1] if len(partes) > 1 else ""
                texto_raw = texto_restante_linha + '\n' + '\n'.join(linhas[1:])
            else:
                titulo_raw = linhas[0]
                texto_raw = '\n'.join(linhas[1:])
                
    titulo = titulo_raw.strip().rstrip(".").upper()
    texto = texto_raw.strip()
    
    slide_dict['titulo'] = titulo
    slide_dict['texto'] = texto

    caminho_atual = slide_dict.get('imagem_limpa_local') or slide_dict.get('arquivo_imagem_local', '')
    if caminho_atual.endswith('_pronto.png'):
        caminho_limpo = caminho_atual.replace('_pronto.png', '.png')
        if os.path.exists(caminho_limpo):
            caminho_atual = caminho_limpo
    
    if not caminho_atual or not os.path.exists(caminho_atual):
        slide_dict['motivo_erro'] = f"Falha na Tipografia: Imagem base não encontrada em '{caminho_atual}'."
        return slide_dict

    try:
        imagem = Image.open(caminho_atual).convert("RGBA")
        largura, altura = imagem.size
        overlay = Image.new("RGBA", imagem.size, (255, 255, 255, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        font_family = config_user.get('fonte_familia', 'Poppins')
        try:
            fonte_titulo_capa = ImageFont.truetype(get_font_path(font_family, 'SemiBold'), config_user.get('tam_capa', 58))
            fonte_titulo_slides = ImageFont.truetype(get_font_path(font_family, 'SemiBold'), config_user.get('tam_titulo', 40))
            fonte_corpo = ImageFont.truetype(get_font_path(font_family, 'Medium'), config_user.get('tam_texto', 28))
            fonte_rodape = ImageFont.truetype(get_font_path(font_family, 'SemiBold'), 20)
        except IOError:
            fonte_titulo_capa = ImageFont.load_default(size=config_user.get('tam_capa', 58))
            fonte_titulo_slides = ImageFont.load_default(size=config_user.get('tam_titulo', 40))
            fonte_corpo = ImageFont.load_default(size=config_user.get('tam_texto', 28))
            fonte_rodape = ImageFont.load_default(size=20)

        cor_texto_geral = config_user.get('cor_texto_rgba', (255, 255, 255, 255))
        cor_capa = config_user.get('cor_capa_rgba', (255, 255, 255, 255))
        cor_destaque = config_user.get('cor_destaque_hex', '#FFD700')
        opacidade = config_user.get('opacidade_fundo', 210)
        cor_fundo_rgba = (0, 0, 0, opacidade)

        # ==============================================================
        # ROTEADOR DE TEMPLATES (Pronto para receber novos designs)
        # ==============================================================
        if "Padrão" in modelo_design:
            
            # --- MODELO PADRÃO: SLIDE 1 (CAPA) ---
            if slide_num == 1:
                texto_capa = "\n".join(textwrap.wrap(titulo if titulo else "ARRASTE PARA LER", width=18))
                texto_corpo_capa = "\n".join(textwrap.wrap(texto, width=35))
                
                h_total = 0
                w_max = 0
                espaco_entre = 30 
                
                if mostrar_titulo and titulo:
                    bbox_capa = draw_overlay.multiline_textbbox((0, 0), texto_capa, font=fonte_titulo_capa, spacing=12)
                    h_total += bbox_capa[3] - bbox_capa[1]
                    w_max = max(w_max, bbox_capa[2] - bbox_capa[0])
                if mostrar_texto and texto:
                    bbox_txt = draw_overlay.multiline_textbbox((0, 0), texto_corpo_capa, font=fonte_corpo, spacing=10)
                    if mostrar_titulo and titulo:
                        h_total += espaco_entre
                    h_total += bbox_txt[3] - bbox_txt[1]
                    w_max = max(w_max, bbox_txt[2] - bbox_txt[0])
                
                padding_y = 50
                padding_x = 60
                h_box = h_total + (padding_y * 2) if h_total > 0 else 0
                w_box = w_max + (padding_x * 2) if w_max > 0 else 0
                
                y_box = altura - h_box - 120
                x_box = (largura - w_box) / 2
                
                if h_box > 0 and mostrar_fundo:
                     draw_overlay.rounded_rectangle([x_box, y_box, x_box + w_box, y_box + h_box], radius=25, fill=cor_fundo_rgba)
                
                y_atual = y_box + padding_y
                
                if mostrar_titulo and titulo:
                    bbox_capa = draw_overlay.multiline_textbbox((0, 0), texto_capa, font=fonte_titulo_capa, spacing=12)
                    w_capa = bbox_capa[2] - bbox_capa[0]
                    x_capa = (largura - w_capa) / 2
                    desenhar_texto_com_sombra(draw_overlay, (x_capa, y_atual), texto_capa, fonte_titulo_capa, cor_capa, spacing=12, align="center")
                    y_atual += (bbox_capa[3] - bbox_capa[1]) + espaco_entre
                    
                if mostrar_texto and texto:
                    bbox_txt = draw_overlay.multiline_textbbox((0, 0), texto_corpo_capa, font=fonte_corpo, spacing=10)
                    w_txt = bbox_txt[2] - bbox_txt[0]
                    x_txt = (largura - w_txt) / 2
                    desenhar_texto_com_sombra(draw_overlay, (x_txt, y_atual), texto_corpo_capa, fonte_corpo, cor_texto_geral, spacing=10, align="center")

            # --- MODELO PADRÃO: SLIDES INTERNOS (2+) ---
            else:
                margem_lateral = 40
                margem_inferior = 80
                padding = 35
                espaco_entre_tit_texto = 35 # Respiro fixo aumentado

                titulo_limpo = ''.join(c for c in titulo if ord(c) < 0x2600) if titulo else ""
                texto_limpo = ''.join(c for c in texto if ord(c) < 0x2600) if texto else ""

                linhas_titulo = []
                for linha in titulo_limpo.split('\n'):
                    linhas_titulo.extend(textwrap.wrap(linha, width=32) if linha.strip() else [''])
                    
                linhas_texto = []
                for paragrafo in texto_limpo.split('\n'):
                    linhas_texto.extend(textwrap.wrap(paragrafo, width=42) if paragrafo.strip() else [''])
                
                texto_titulo_formatado = "\n".join(linhas_titulo)
                texto_corpo_formatado = "\n".join(linhas_texto)
                
                h_total_conteudo = 0
                if mostrar_titulo and titulo:
                    bbox_tit = draw_overlay.multiline_textbbox((0,0), texto_titulo_formatado, font=fonte_titulo_slides, spacing=8)
                    # Trava a altura considerando a métrica total da fonte (evita o problema do 'g')
                    h_total_conteudo += max((bbox_tit[3] - bbox_tit[1]), fonte_titulo_slides.size)
                if mostrar_texto and texto:
                    bbox_txt = draw_overlay.multiline_textbbox((0,0), texto_corpo_formatado, font=fonte_corpo, spacing=10)
                    if mostrar_titulo and titulo:
                        h_total_conteudo += espaco_entre_tit_texto
                    h_total_conteudo += max((bbox_txt[3] - bbox_txt[1]), fonte_corpo.size)
                
                altura_card = h_total_conteudo + (padding * 2) if h_total_conteudo > 0 else 0
                
                if altura_card > 0:
                    y_box = altura - margem_inferior - altura_card
                    x_box = margem_lateral
                    w_box = largura - (margem_lateral * 2)
                    
                    if mostrar_fundo:
                        draw_overlay.rounded_rectangle([x_box, y_box, x_box + w_box, y_box + altura_card], radius=25, fill=cor_fundo_rgba)
                        espessura_barra = 6
                        draw_overlay.rounded_rectangle([x_box, y_box + padding, x_box + espessura_barra, y_box + altura_card - padding], radius=3, fill=cor_destaque)
                    
                    y_atual = y_box + padding
                    x_texto = x_box + padding + 10
                    
                    if mostrar_titulo and titulo:
                        desenhar_texto_com_sombra(draw_overlay, (x_texto, y_atual), texto_titulo_formatado, fonte_titulo_slides, cor_texto_geral, offset=(2, 2), spacing=8, align="left")
                        bbox_tit = draw_overlay.multiline_textbbox((0,0), texto_titulo_formatado, font=fonte_titulo_slides, spacing=8)
                        y_atual += max((bbox_tit[3] - bbox_tit[1]), fonte_titulo_slides.size) + espaco_entre_tit_texto
                        
                    if mostrar_texto and texto:
                        desenhar_texto_com_sombra(draw_overlay, (x_texto, y_atual), texto_corpo_formatado, fonte_corpo, cor_texto_geral, offset=(2, 2), spacing=10, align="left")
        
        
        # ==============================================================
        # FUTUROS MODELOS DE DESIGN PODEM SER INSERIDOS AQUI (elif "Minimalista"...)
        # ==============================================================

        # --- MESCLA AS CAMADAS ---
        imagem = Image.alpha_composite(imagem, overlay)
        draw_final = ImageDraw.Draw(imagem)
        
        # --- RODAPÉ UNIVERSAL (Aparece em todos os modelos) ---
        if slide_num == 1:
            rodape_texto = "Deslize para ler >"
            bbox_rodape = draw_final.textbbox((0, 0), rodape_texto, font=fonte_rodape)
            x_rodape = (largura - (bbox_rodape[2] - bbox_rodape[0])) / 2
            desenhar_texto_com_sombra(draw_final, (x_rodape, altura - 50), rodape_texto, fonte_rodape, (255, 255, 255, 200))
        else:
            paginacao_texto = f"{slide_num:02d} • {total_slides:02d}"
            desenhar_texto_com_sombra(draw_final, (largura - 40 - 80, altura - 50), paginacao_texto, fonte_rodape, (200, 200, 200, 255))
            
            texto_marca = "@" + config_user.get('marca_nome', "EstudioIA")
            desenhar_texto_com_sombra(draw_final, (40, altura - 50), texto_marca, fonte_rodape, (200, 200, 200, 255))

        caminho_final = caminho_atual.replace('.png', '_pronto.png')
        imagem.convert("RGB").save(caminho_final, "PNG")

        slide_dict.update({'arquivo_imagem_local': caminho_final, 'imagem_limpa_local': caminho_atual, 'status_imagem': "Diagramada com Sucesso"})
        slide_dict.pop('motivo_erro', None)
        return slide_dict

    except Exception as e:
        slide_dict['motivo_erro'] = f"Falha na Tipografia: Erro de desenho ({e})."
        return slide_dict

def gerar_imagem_para_slide(slide_dict: dict, index_slide: int, output_dir: str, config_user: dict = None, mock_client=None) -> dict:
    load_dotenv()
    api_key = st.secrets["GEMINI_API_KEY"]
    if not api_key:
        return {'status_imagem': "Erro", 'motivo_erro': "GEMINI_API_KEY não encontrada!"}
        
    client = genai.Client(api_key=api_key)
    slide_num = slide_dict.get('slide_numero') or index_slide + 1
    
    conteudo_bruto_do_slide = json.dumps(slide_dict, ensure_ascii=False)
    prompt_descricao = (
        f"Você é um diretor de arte criando o fundo (background) de um carrossel de Instagram. "
        f"Aqui está o roteiro completo deste slide: {conteudo_bruto_do_slide}. "
        f"Com base nesse texto, crie uma arte conceitual e profissional que represente este exato tema. "
        f"REGRA ABSOLUTA: NÃO escreva nenhuma letra, palavra ou número na imagem. Deixe o fundo limpo para receber tipografia. Formato centralizado."
    )

    instrucao_custom = slide_dict.get('instrucao_imagem', '').strip()
    if instrucao_custom:
        prompt_descricao += f" REGRA ESPECIAL DO USUÁRIO APENAS PARA ESTA IMAGEM: {instrucao_custom}"
        
    caminho_base = os.path.join(output_dir, f"slide_{slide_num}_raw.png")
    
    formato_desejado = config_user.get('formato_imagem', '1080 x 1080 px (Quadrado)') if config_user else '1080'
    proporcao_ia = "3:4" if "1440" in formato_desejado else "1:1"

    try:
        response = client.models.generate_content(
            model='models/gemini-3.1-flash-image',
            contents=prompt_descricao,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                aspect_ratio=proporcao_ia # Força a IA a criar no tamanho certo
            )
        )
        
        # Log de Tokens e Custo da Regeração (Modelo de Imagem)
        tokens_in = getattr(response.usage_metadata, 'prompt_token_count', 0) if getattr(response, 'usage_metadata', None) else 0
        tokens_out = getattr(response.usage_metadata, 'candidates_token_count', 0) if getattr(response, 'usage_metadata', None) else 0
        custo_refacao = (tokens_in * (0.50 / 1_000_000)) + (tokens_out * (60.00 / 1_000_000))
        
        print(f"🪙 [REGERAÇÃO DE IMAGEM] In: {tokens_in} | Out: {tokens_out} | Custo: US$ {custo_refacao:.5f}")

        imagem_bytes = None
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    imagem_bytes = part.inline_data.data
                    break

        if imagem_bytes:
            imagem_pil = Image.open(BytesIO(imagem_bytes)).convert("RGBA")
            width, height = imagem_pil.size
            
            # --- LEITURA DO PLANO PREMIUM ---
            formato_desejado = config_user.get('formato_imagem', '1080 x 1080 px (Quadrado)') if config_user else '1080'
            
            if '1440' in formato_desejado:
                target_w, target_h = 1080, 1440
            else:
                target_w, target_h = 1080, 1080
                
            target_ratio = target_w / target_h
            img_ratio = width / height

            # --- A GUILHOTINA DINÂMICA ---
            if img_ratio > target_ratio:
                # Imagem é mais larga que o necessário (Cortar as laterais)
                new_width = int(height * target_ratio)
                left = (width - new_width) // 2
                top = 0
                right = left + new_width
                bottom = height
            else:
                # Imagem é mais alta que o necessário (Cortar em cima/baixo)
                new_height = int(width / target_ratio)
                left = 0
                top = (height - new_height) // 2
                right = width
                bottom = top + new_height
            
            imagem_pil = imagem_pil.crop((left, top, right, bottom))
            imagem_pil = imagem_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)
            imagem_pil.save(caminho_base)
            
            slide_dict.update({
                'arquivo_imagem_local': caminho_base, 
                'imagem_limpa_local': caminho_base,
                'status_imagem': "Gerada com Sucesso"
            })
            return slide_dict
        else:
            slide_dict.update({'status_imagem': "Erro", 'motivo_erro': "O Google não retornou os pixels da imagem."})
            return slide_dict

    except Exception as e:
        slide_dict.update({'status_imagem': "Erro", 'motivo_erro': str(e)})
        return slide_dict

def regerar_slide_individual(slide_dict: dict, index_slide: int, config_user: dict = None) -> dict:
    print(f"\n💥 Iniciando regeração completa para o slide {index_slide + 1}...")
    output_dir = os.path.dirname(slide_dict.get('arquivo_imagem_local', '')) or os.path.join("imagens_carrossel", time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(output_dir, exist_ok=True)
    slide_com_imagem = gerar_imagem_para_slide(slide_dict, index_slide, output_dir, config_user)
    if slide_com_imagem.get("status_imagem") != "Gerada com Sucesso":
        return slide_com_imagem
    return aplicar_tipografia_slide(slide_com_imagem, config_user)


# ==========================================
# AGENTES PRINCIPAIS DA ESTEIRA
# ==========================================

def run_agent_1(tema_input: str, client: Any, model: str, config_user: dict = None) -> Dict[str, Any] | None:
    if config_user is None:
        config_user = {}
    tom_de_voz = config_user.get('tom_de_voz', 'Viral & Clickbait')
    qtd_slides = config_user.get('qtd_slides', 6)

    response_text = ""
    try:
        prompt_base = prompts.PROMPT_AGENT_1_URL if tema_input.startswith("http") else prompts.PROMPT_AGENT_1
        regra_slides = f"Você DEVE gerar exatamente {qtd_slides} slides no roteiro e no array JSON.\n\n"

        if "**TEMA DE ENTRADA:**" in prompt_base:
            prompt_injetado = prompt_base.replace("**TEMA DE ENTRADA:**", f"""{regra_slides}**TOM DE VOZ DA REDAÇÃO:**\nO tom de voz deve ser estritamente: [{tom_de_voz}]\n\n**TEMA DE ENTRADA:**""")
        else:
            prompt_injetado = prompt_base.replace("**URL PARA ANÁLISE:**", f"""{regra_slides}**TOM DE VOZ DA REDAÇÃO:**\nO tom de voz deve ser estritamente: [{tom_de_voz}]\n\n**URL PARA ANÁLISE:**""")
        
        prompt = prompt_injetado.format(tema_input=tema_input, url=tema_input)
        response = client.models.generate_content(model='gemini-3.6-flash', contents=prompt, config=genai.types.GenerateContentConfig(response_mime_type="application/json"))
        
        # LOG DE TOKENS E CUSTO - AGENTE 1 (Modelo de Texto 3.6 Flash)
        tokens_in = getattr(response.usage_metadata, 'prompt_token_count', 0) if getattr(response, 'usage_metadata', None) else 0
        tokens_out = getattr(response.usage_metadata, 'candidates_token_count', 0) if getattr(response, 'usage_metadata', None) else 0
        total_tokens = tokens_in + tokens_out
        custo_a1 = (tokens_in * (1.50 / 1_000_000)) + (tokens_out * (7.50 / 1_000_000))
        
        print("\n" + "="*60)
        print(f"🪙 [AGENTE 1 - ESTRATEGISTA] In: {tokens_in} | Out: {tokens_out} | Custo: US$ {custo_a1:.5f}")

        if not response.text:
            return None

        response_text = response.text
        resultado = limpar_e_decodificar_json(response_text)
        resultado['_tokens_acumulados'] = total_tokens 
        resultado['_custo_acumulado'] = custo_a1
        return resultado

    except Exception as e:
        print(f"Erro no Agente 1: {e}")
        return None

def run_agent_2(briefing_agent_1: Dict[str, Any], client: Any, model: str, config_user: dict = None) -> Dict[str, Any] | None:
    if config_user is None:
        config_user = {}
    qtd_slides = config_user.get('qtd_slides', 6)
    
    response_text = ""
    try:
        briefing_str = json.dumps(briefing_agent_1, indent=2, ensure_ascii=False)
        prompt_base = prompts.PROMPT_AGENT_2
        
        regra_qtd = (
            f"Você DEVE gerar exatamente {qtd_slides} slides no roteiro.\n"
            "REGRA ESTRUTURAL OBRIGATÓRIA: O JSON final DEVE ser um objeto contendo UMA chave principal chamada EXATAMENTE 'roteiro_carrossel'."
        )
        prompt_injetado = f"{regra_qtd}\n\n{prompt_base}".replace(
            "crie um roteiro detalhado para um carrossel de 5 a 7 slides",
            f"crie um roteiro detalhado para um carrossel de {qtd_slides} slides"
        )
        
        prompt = prompt_injetado.format(briefing_agent_1=briefing_str)
        response = client.models.generate_content(model='gemini-3.6-flash', contents=prompt, config=genai.types.GenerateContentConfig(response_mime_type="application/json"))
        
        # LOG DE TOKENS E CUSTO - AGENTE 2 (Modelo de Texto 3.6 Flash)
        tokens_in = getattr(response.usage_metadata, 'prompt_token_count', 0) if getattr(response, 'usage_metadata', None) else 0
        tokens_out = getattr(response.usage_metadata, 'candidates_token_count', 0) if getattr(response, 'usage_metadata', None) else 0
        custo_a2 = (tokens_in * (1.50 / 1_000_000)) + (tokens_out * (7.50 / 1_000_000))
        
        tokens_acumulados = briefing_agent_1.get('_tokens_acumulados', 0) + tokens_in + tokens_out
        custo_acumulado = briefing_agent_1.get('_custo_acumulado', 0.0) + custo_a2
        
        print(f"🪙 [AGENTE 2 - COPYWRITER] In: {tokens_in} | Out: {tokens_out} | Custo: US$ {custo_a2:.5f}")

        if not response.text:
            return None

        response_text = response.text
        resultado = limpar_e_decodificar_json(response_text)
        resultado['_tokens_acumulados'] = tokens_acumulados
        resultado['_custo_acumulado'] = custo_acumulado
        return resultado
        
    except Exception as e:
        print(f"Erro no Agente 2: {e}")
        return None

def run_agent_3_image_creator(draft, status, output_dir, config_user=None):
    load_dotenv()
    api_key = st.secrets["GEMINI_API_KEY"]
    if not api_key:
        raise Exception("GEMINI_API_KEY não encontrada no .env!")
        
    client = genai.Client(api_key=api_key)
    roteiro = draft.get('roteiro_carrossel', [])
    qtd_slides = len(roteiro)
    
    tokens_in_total = 0
    tokens_out_total = 0
    custo_a3_total = 0.0 

    for index, slide in enumerate(roteiro):
        if status:
            status.update(label=f"🎨 Agente 3: Gerando arte {index + 1} de {qtd_slides}...", state="running")

        conteudo_bruto_do_slide = json.dumps(slide, ensure_ascii=False)
        prompt_descricao = (
            f"Você é um diretor de arte criando o fundo (background) de um carrossel de Instagram. "
            f"Aqui está o roteiro completo deste slide: {conteudo_bruto_do_slide}. "
            f"Com base nesse texto, crie uma arte conceitual e profissional que represente este exato tema. "
            f"REGRA ABSOLUTA 1: NÃO escreva nenhuma letra, palavra ou número na imagem. Deixe o fundo limpo para receber tipografia. Formato centralizado."
        )

        caminho_raw = os.path.join(output_dir, f"slide_{index + 1}_raw.png")

        try:
            response = client.models.generate_content(
                model='models/gemini-3.1-flash-image',
                contents=prompt_descricao,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"])
            )
            
            # Somando tokens e custo desta imagem específica (Modelo 3.1 Flash Image)
            t_in = getattr(response.usage_metadata, 'prompt_token_count', 0) if getattr(response, 'usage_metadata', None) else 0
            t_out = getattr(response.usage_metadata, 'candidates_token_count', 0) if getattr(response, 'usage_metadata', None) else 0
            custo_img = (t_in * (0.50 / 1_000_000)) + (t_out * (60.00 / 1_000_000))
            
            tokens_in_total += t_in
            tokens_out_total += t_out
            custo_a3_total += custo_img

            imagem_bytes = None
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        imagem_bytes = part.inline_data.data
                        break

            if imagem_bytes:
                imagem_pil = Image.open(BytesIO(imagem_bytes)).convert("RGBA")
                width, height = imagem_pil.size
                
                # --- LEITURA DO PLANO PREMIUM ---
                formato_desejado = config_user.get('formato_imagem', '1080 x 1080 px (Quadrado)') if config_user else '1080'
                
                if '1440' in formato_desejado:
                    target_w, target_h = 1080, 1440
                else:
                    target_w, target_h = 1080, 1080
                    
                target_ratio = target_w / target_h
                img_ratio = width / height

                # --- A GUILHOTINA DINÂMICA ---
                if img_ratio > target_ratio:
                    # Imagem é mais larga que o necessário (Cortar as laterais)
                    new_width = int(height * target_ratio)
                    left = (width - new_width) // 2
                    top = 0
                    right = left + new_width
                    bottom = height
                else:
                    # Imagem é mais alta que o necessário (Cortar em cima/baixo)
                    new_height = int(width / target_ratio)
                    left = 0
                    top = (height - new_height) // 2
                    right = width
                    bottom = top + new_height
                
                imagem_pil = imagem_pil.crop((left, top, right, bottom))
                imagem_pil = imagem_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)
                imagem_pil.save(caminho_raw)
                
                slide.update({
                    'status_imagem': "Gerada com Sucesso",
                    'arquivo_imagem_local': caminho_raw,
                    'imagem_limpa_local': caminho_raw
                })
            else:
                raise Exception("Pixels não retornados.")

        except Exception as e:
            print(f"⚠️ Erro no slide {index + 1}: {e}")
            imagem_pil = Image.new('RGBA', (1080, 1080), (139, 0, 0, 255))
            slide.update({'status_imagem': "Gerada com Sucesso", 'caminho_imagem': caminho_raw, 'caminho_fundo': caminho_raw})

    # LOG DE TOKENS E CUSTO FINAL - AGENTE 3
    tokens_acumulados = draft.get('_tokens_acumulados', 0) + tokens_in_total + tokens_out_total
    custo_acumulado = draft.get('_custo_acumulado', 0.0) + custo_a3_total
    
    draft['_tokens_acumulados'] = tokens_acumulados
    draft['_custo_acumulado'] = custo_acumulado
    
    print(f"🪙 [AGENTE 3 - DIRETOR DE ARTE] In: {tokens_in_total} | Out: {tokens_out_total} | Custo (Pelas {qtd_slides} Imagens): US$ {custo_a3_total:.5f}")

    return draft

def run_agent_4_typographer(draft: dict, status_log, config_user: dict = None) -> dict:
    status_log.write("✍️ Agente 4: Aplicando tipografia...")
    roteiro_final = []
    slides_para_diagramar = draft.get("roteiro_carrossel", [])
    for i, slide in enumerate(slides_para_diagramar, start=1):
        if slide.get("status_imagem") == "Gerada com Sucesso":
            slide_final = aplicar_tipografia_slide(slide, config_user)
            roteiro_final.append(slide_final)
        else:
            roteiro_final.append(slide)
    draft["roteiro_carrossel"] = roteiro_final
    return draft

def run_agent_5_reviewer(draft: Dict[str, Any], client: Any, model: str = None, config_user: dict = None) -> Dict[str, Any]:
    try:
        content_str = json.dumps(draft, indent=2, ensure_ascii=False)
        prompt = prompts.PROMPT_AGENT_5_EDITOR.format(content_to_review=content_str)
        response = client.models.generate_content(model='gemini-3.6-flash', contents=prompt, config=genai.types.GenerateContentConfig(response_mime_type="application/json"))
        
        # LOG DE TOKENS, CUSTOS E EXTRATO FINAL
        tokens_in = getattr(response.usage_metadata, 'prompt_token_count', 0) if getattr(response, 'usage_metadata', None) else 0
        tokens_out = getattr(response.usage_metadata, 'candidates_token_count', 0) if getattr(response, 'usage_metadata', None) else 0
        custo_a5 = (tokens_in * (1.50 / 1_000_000)) + (tokens_out * (7.50 / 1_000_000))
        
        tokens_acumulados_final = draft.get('_tokens_acumulados', 0) + tokens_in + tokens_out
        custo_acumulado_final = draft.get('_custo_acumulado', 0.0) + custo_a5
        
        print(f"🪙 [AGENTE 5 - REVISOR CHEFE] In: {tokens_in} | Out: {tokens_out} | Custo: US$ {custo_a5:.5f}")
        print(f"🏁 [FIM DA ESTEIRA] TOTAL DE TOKENS: {tokens_acumulados_final} | CUSTO TOTAL DA OPERAÇÃO: US$ {custo_acumulado_final:.5f}")
        print("="*60 + "\n")

        if not response.text:
            draft['parecer_revisor'] = {'status': 'ERRO NA REVISÃO'}
            return draft

        draft_revisado = limpar_e_decodificar_json(response.text)
        
        # Repassa o caminho das imagens geradas para a maleta revisada
        for i, slide in enumerate(draft_revisado.get('roteiro_carrossel', [])):
            if i < len(draft.get('roteiro_carrossel', [])):
                slide['arquivo_imagem_local'] = draft['roteiro_carrossel'][i].get('arquivo_imagem_local')
                slide['imagem_limpa_local'] = draft['roteiro_carrossel'][i].get('imagem_limpa_local')
                slide['status_imagem'] = draft['roteiro_carrossel'][i].get('status_imagem')

        draft_revisado['_tokens_acumulados'] = tokens_acumulados_final
        draft_revisado['_custo_acumulado'] = custo_acumulado_final

        return draft_revisado

    except Exception as e:
        draft['parecer_revisor'] = {'status': 'ERRO', 'correcoes_realizadas': [str(e)]}
        return draft
