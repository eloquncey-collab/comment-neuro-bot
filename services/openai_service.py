import openai
from config import settings
import logging

openai.api_key = settings.OPENAI_API_KEY

async def generate_comment(post_text: str, prompt_type: str, custom_prompt: str = None) -> str:
    try:
        system_prompts = {
            "short": "Напиши короткий (до 15 слов) осмысленный комментарий к посту.",
            "long": "Напиши развернутый и полезный комментарий к посту (3-5 предложений).",
            "friendly": "Напиши очень дружелюбный и позитивный комментарий.",
            "provocative": "Напиши провокационный комментарий, который вызовет дискуссию.",
            "intimate": "Напиши немного флиртующий и игривый комментарий."
        }

        sys_instruction = system_prompts.get(prompt_type, system_prompts["short"])
        if custom_prompt:
            sys_instruction = custom_prompt

        response = openai.chat.completions.create(
            model="gpt-3.5-turbo", # Или gpt-4
            messages=[
                {"role": "system", "content": sys_instruction},
                {"role": "user", "content": f"Текст поста: {post_text}"}
            ],
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI Error: {e}")
        return "Интересный пост!"