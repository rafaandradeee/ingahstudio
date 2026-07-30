import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega as variáveis do arquivo .env
load_dotenv()

# Conecta com o Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("⚠️ Chaves do Supabase não encontradas no arquivo .env!")

supabase: Client = create_client(url, key)

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