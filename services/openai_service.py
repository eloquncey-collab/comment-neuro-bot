import openai
import config

openai.api_key = config.OPENAI_API_KEY

async def generate_comment(post_text, prompt_type):
    """
    Генерирует комментарий на основе текста поста и типа промпта.
    """
    try:
        # Формируем системный промпт
        system_prompt = f"Ты опытный комментатор Telegram. Твоя задача: {prompt_type}. Не используй эмодзи, если это не требуется. пиши на русском языке."
        
        # Ограничиваем длину контекста, чтобы сэкономить токены
        context = post_text[:1000] if post_text else "Без текста"

        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Пост: {context}\n\nНапиши комментарий:"}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return "Интересный пост!"