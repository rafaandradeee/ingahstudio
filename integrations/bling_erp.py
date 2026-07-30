"""
Módulo de Integração com a API v3 do Bling ERP.

Responsável por buscar a lista de produtos ativos e seus estoques.
Se o token da API não for fornecido, retorna uma lista de produtos mockada.
"""

import requests
import json

def _get_mock_products():
    """Retorna uma lista de produtos simulada para fins de desenvolvimento e teste."""
    print("Aviso: Token do Bling não configurado. Usando lista de produtos simulada.")
    return [
        {"nome": "Cultura Líquida - Cogumelo Shimeji", "estoque": 50},
        {"nome": "Cultura Líquida - Cogumelo Portobello", "estoque": 35},
        {"nome": "Spawn (Semente) de Cogumelo Ostra em Grãos", "estoque": 120},
        {"nome": "Saco Autoclavável com Filtro para Cultivo (Unidade)", "estoque": 500},
        {"nome": "Placas de Petri Estéreis com Meio BDA (Kit com 10)", "estoque": 80},
        {"nome": "Pó de Serragem Tratada para Substrato (1kg)", "estoque": 25},
        {"nome": "Fibra de Coco Esterilizada (500g)", "estoque": 40},
    ]

def get_products_from_bling(api_token: str | None) -> list[dict]:
    """
    Busca produtos na API v3 do Bling ou retorna uma lista mock.

    Args:
        api_token: O token da API do Bling. Se for None ou vazio,
                   a função de mock é chamada.

    Returns:
        Uma lista de dicionários, onde cada dicionário representa um produto
        com as chaves 'nome' e 'estoque'.
    """
    if not api_token:
        return _get_mock_products()

    print("Buscando produtos na API do Bling ERP...")
    url = "https://www.bling.com.br/api/v3/produtos"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_token}",
    }
    params = {
        "limite": 100,  # Limite de produtos por página
        "criterio": 1,  # 1 para Ativos
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()  # Lança um erro para status HTTP 4xx/5xx

        data = response.json().get("data", [])
        
        if not data:
            print("Nenhum produto encontrado no Bling. Usando mock.")
            return _get_mock_products()

        # Extrai e formata apenas os dados que precisamos
        product_list = [
            {
                "nome": item.get("nome", "Nome Indisponível"),
                "estoque": item.get("saldo", 0) # API v3 usa 'saldo' para estoque
            }
            for item in data
        ]
        
        print(f"{len(product_list)} produtos encontrados no Bling.")
        return product_list

    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar com a API do Bling: {e}")
        print("Continuando a execução com a lista de produtos simulada.")
        return _get_mock_products()
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao processar dados do Bling: {e}")
        return _get_mock_products()
