"""
Módulo de Configuração.

Carrega as variáveis de ambiente a partir de um arquivo .env e configura
as chaves de API e outros parâmetros necessários para a aplicação.
"""

import os
import sys
from dotenv import load_dotenv

def load_configurations():
    """Carrega as variáveis de ambiente e configura a API do Gemini."""
    load_dotenv()

    # --- Carregamento das Chaves e Tokens ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    BLING_API_TOKEN = os.getenv("BLING_API_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")

    # --- Validação e Configuração ---
    if not GEMINI_API_KEY:
        print("Erro: A variável de ambiente GEMINI_API_KEY não foi encontrada.")
        print("Por favor, crie um arquivo .env e adicione sua chave de API.")
        sys.exit(1) # Encerra o script se a chave principal não estiver presente

    # --- Definição do Modelo ---
    GEMINI_MODEL = "gemini-3.6-flash"

    # Retorna um dicionário com as configurações carregadas
    return {
        "gemini_api_key": GEMINI_API_KEY,
        "bling_api_token": BLING_API_TOKEN,
        "webhook_url": WEBHOOK_URL,
        "gemini_model": GEMINI_MODEL
    }

# Carrega as configurações no momento da importação do módulo
# para que estejam disponíveis em toda a aplicação.
CONFIG = load_configurations()
