"""
Módulo Gerenciador de Saída.

Responsável por salvar o conteúdo final em arquivos locais e
enviar para serviços externos via webhook.
"""

import os
import requests
from datetime import datetime

def save_to_markdown(content: str, output_dir: str = "posts_gerados") -> str | None:
    """
    Salva o conteúdo fornecido em um arquivo Markdown.

    O nome do arquivo é formatado com a data atual (YYYY-MM-DD).

    Args:
        content: O texto a ser salvo no arquivo.
        output_dir: O diretório onde o arquivo será salvo.

    Returns:
        O caminho do arquivo salvo ou None em caso de erro.
    """
    try:
        # Garante que o diretório de saída exista
        os.makedirs(output_dir, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        file_name = f"carrossel_{date_str}.md"
        file_path = os.path.join(output_dir, file_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Conteúdo salvo com sucesso em: {file_path}")
        return file_path
    except IOError as e:
        print(f"Erro ao salvar o arquivo Markdown: {e}")
        return None
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao salvar o arquivo: {e}")
        return None

def send_to_webhook(content: str, webhook_url: str | None):
    """
    Envia o conteúdo para uma URL de webhook.

    Args:
        content: O texto a ser enviado.
        webhook_url: A URL do webhook. Se for None ou vazia, a função não faz nada.
    """
    if not webhook_url:
        print("URL de Webhook não configurada. Etapa de envio ignorada.")
        return

    print(f"Enviando conteúdo para o webhook: {webhook_url[:30]}...")
    headers = {
        "Content-Type": "application/json"
    }
    # O payload pode ser ajustado conforme a necessidade do seu serviço (Make, n8n, etc.)
    # Geralmente, um objeto com uma chave "text" ou "content" é suficiente.
    payload = {
        "text": content,
        "source": "Equipe_IA_Cogumelos"
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        print("Conteúdo enviado para o webhook com sucesso!")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar para o webhook: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado no envio para o webhook: {e}")
