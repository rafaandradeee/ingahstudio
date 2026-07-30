"""
Testes para o módulo de agentes.
"""

import pytest
from agents.equipe import _clean_json_response

# Casos de teste para a função _clean_json_response
@pytest.mark.parametrize("raw_text, expected_json_str", [
    # Caso 1: JSON limpo em um bloco de código
    (
        '''```json
{
  "key": "value"
}
```''',
        '''{
  "key": "value"
}'''
    ),
    # Caso 2: JSON limpo sem a tag "json"
    (
        '''```
{
  "key": "value"
}
```''',
        '''{
  "key": "value"
}'''
    ),
    # Caso 3: JSON com texto antes e depois, dentro de um bloco de código
    (
        '''Aqui está o JSON:
```json
{
  "key": "value"
}
```
Espero que ajude!''',
        '''{
  "key": "value"
}'''
    ),
    # Caso 4: JSON puro, sem bloco de código, com espaços
    (
        '''  {
    "key": "value"
  }  ''',
        '''{
    "key": "value"
  }'''
    ),
    # Caso 5: JSON com texto antes, mas sem bloco de código
    (
        '''Aqui está o JSON: {
  "key": "value"
}''',
        '''{
  "key": "value"
}'''
    ),
    # Caso 6: JSON com texto depois, mas sem bloco de código
    (
        '''{
  "key": "value"
} Espero que ajude!''',
        '''{
  "key": "value"
}'''
    ),
    # Caso 7: JSON com texto antes e depois, sem bloco de código
    (
        '''Claro! O JSON é {
  "key": "value"
}, use com sabedoria.''',
        '''{
  "key": "value"
}'''
    ),
    # Caso 8: String vazia
    (
        '',
        ''
    ),
    # Caso 9: String sem JSON
    (
        'Isso não é um JSON.',
        'Isso não é um JSON.'
    ),
    # Caso 10: JSON mal formado (faltando '}')
    (
        '''{
  "key": "value"
''',
        '''{
  "key": "value"'''
    ),
    # Caso 11: JSON com múltiplos objetos (deve pegar do primeiro '{' ao último '}')
    (
        '{"a": 1} ... {"b": 2}',
        '{"a": 1} ... {"b": 2}'
    ),
    # Caso 12: Aquele que causa o erro reportado pelo usuário
    (
        '''
  "pilar_conteudo": "fake pilar"''',
        '"pilar_conteudo": "fake pilar"'
    )
])
def test_clean_json_response(raw_text, expected_json_str):
    """Testa a função _clean_json_response com diferentes formatos de entrada."""
    cleaned_text = _clean_json_response(raw_text)
    assert cleaned_text == expected_json_str
