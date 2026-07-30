import os
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

# Tenta carregar o .env local (caso esteja rodando na sua máquina)
load_dotenv()

# Pega do Streamlit Secrets se estiver na nuvem, ou do ambiente local se estiver na sua máquina
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
except (FileNotFoundError, KeyError, Exception):
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("⚠️ Chaves do Supabase não encontradas! Verifique o .env ou os Secrets do Streamlit.")

supabase: Client = create_client(url, key)

# Log de sucesso (aparece no terminal e na tela)
print("✅ Conexão com o Supabase estabelecida com sucesso!")
st.sidebar.success("Banco de dados conectado!")

def get_user_wallet(user_id: str):
    """Busca a carteira de créditos do usuário."""
    try:
        response = supabase.table('wallets').select('*').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Erro ao buscar carteira: {e}")
        return None

def descontar_creditos(user_id: str, custo: int):
    """Desconta os créditos da carteira após a geração."""
    carteira = get_user_wallet(user_id)
    if not carteira:
        return False, "Carteira não encontrada."
    
    creditos_plano = carteira.get('creditos_plano', 0)
    creditos_avulsos = carteira.get('creditos_avulsos', 0)
    
    # Lógica de cobrança: gasta o avulso primeiro, depois o do plano
    if creditos_avulsos >= custo:
        novo_avulso = creditos_avulsos - custo
        novo_plano = creditos_plano
    elif (creditos_avulsos + creditos_plano) >= custo:
        resto = custo - creditos_avulsos
        novo_avulso = 0
        novo_plano = creditos_plano - resto
    else:
        return False, "Créditos insuficientes."

    # Atualiza no banco
    try:
        supabase.table('wallets').update({
            'creditos_plano': novo_plano,
            'creditos_avulsos': novo_avulso
        }).eq('user_id', user_id).execute()
        return True, "Créditos descontados com sucesso."
    except Exception as e:
        print(f"Erro ao descontar créditos: {e}")
        return False, f"Erro interno: {e}"

def get_user_settings(user_id: str):
    """Busca as preferências visuais do usuário."""
    try:
        response = supabase.table('user_settings').select('*').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Erro ao buscar configurações: {e}")
        return None
