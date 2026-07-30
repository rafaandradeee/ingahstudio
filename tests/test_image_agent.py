import pytest
from unittest.mock import MagicMock, patch
import os
from io import BytesIO
from PIL import Image

# Import the function to be tested
from agents.equipe import run_agent_3_image_creator

# Define the actual output directory used by the agent
ACTUAL_IMAGE_DIR = "imagens_carrossel"

@pytest.fixture(autouse=True)
def cleanup_actual_image_dir():
    """Fixture to clean up the actual image directory before and after tests."""
    import shutil
    if os.path.exists(ACTUAL_IMAGE_DIR):
        shutil.rmtree(ACTUAL_IMAGE_DIR, ignore_errors=True)
    yield
    if os.path.exists(ACTUAL_IMAGE_DIR):
        shutil.rmtree(ACTUAL_IMAGE_DIR, ignore_errors=True)

@patch('PIL.Image.open')
def test_run_agent_3_image_creator_mushroom_theme(
    mock_image_open
):
    """
    Test the run_agent_3_image_creator with a 'mushroom' theme, ensuring:
    - The client's generate_images method is called.
    - The prompt contains the 'mushroom' theme.
    - An image file is "saved" (mocked).
    - The returned draft indicates successful image generation.
    """
    
    # Mock the genai client and its methods
    mock_client = MagicMock()
    
    # Create a mock image object that has an image_bytes attribute
    mock_image_bytes = b"mock_image_data"
    mock_generated_image = MagicMock()
    mock_generated_image.image.image_bytes = mock_image_bytes

    # Configure the interaction mock
    mock_interaction = MagicMock()
    mock_step = MagicMock()
    mock_part = MagicMock()
    # Assume image is returned in part.image.image_bytes
    mock_part.image.image_bytes = mock_image_bytes
    mock_step.model_turn.parts = [mock_part]
    mock_interaction.steps = [mock_step]
    
    mock_client.interactions.create.return_value = mock_interaction
    
    # Mock the Image.open to return a mock image object with a save method
    mock_pil_image = MagicMock()
    mock_image_open.return_value = mock_pil_image

    # Define the input draft with a "cogumelo" visual direction
    draft_input = {
        "roteiro_carrossel": [
            {
                "slide_numero": 1,
                "direcionamento_visual": "cogumelo",
                "texto_slide": "Texto do slide 1"
            }
        ]
    }

    # Execute the function
    result_draft = run_agent_3_image_creator(draft_input, MagicMock(), ACTUAL_IMAGE_DIR, mock_client=mock_client)

    # Assertions
    assert result_draft is not None
    assert "roteiro_carrossel" in result_draft
    assert len(result_draft["roteiro_carrossel"]) == 1

    generated_slide = result_draft["roteiro_carrossel"][0]
    assert "arquivo_imagem_local" in generated_slide
    assert generated_slide["arquivo_imagem_local"].startswith(os.path.join(ACTUAL_IMAGE_DIR, "slide_1"))
    assert generated_slide["status_imagem"] == "Gerada com Sucesso (PRO)"

    # Verify interactions.create was called with the correct arguments
    mock_client.interactions.create.assert_called_once()
    call_args, call_kwargs = mock_client.interactions.create.call_args
    
    assert call_kwargs['model'] == 'models/gemini-3.1-flash-image'
    # Check if 'cogumelo' is in the prompt
    assert "cogumelo" in call_kwargs['input']
    assert "STRICT INSTRUCTION: NO TEXT" in call_kwargs['input']

    assert 'response_modalities' in call_kwargs
    assert call_kwargs['response_modalities'] == ['image', 'text']
    
    # Verify Image.open was called with a BytesIO object containing the mock image bytes
    mock_image_open.assert_called_once()
    called_args, _ = mock_image_open.call_args
    assert isinstance(called_args[0], BytesIO)
    assert called_args[0].getvalue() == mock_image_bytes
    
    # Verify the save method on the PIL Image object was called
    mock_pil_image.save.assert_called_once()
    assert mock_pil_image.save.call_args[0][0].startswith(os.path.join(ACTUAL_IMAGE_DIR, "slide_1"))
