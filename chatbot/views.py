from rest_framework.decorators import api_view
from rest_framework.response import Response
import openai
from django.conf import settings
import os

# Create a Client instance with your API key
client = openai.Client(api_key=os.getenv('OPENAI_API_KEY'))

@api_view(['POST'])
def chatbot_response(request):
    user_message = request.data.get('message', '')

    if not user_message:
        return Response({"error": "Message is required"}, status=400)

    # Retrieve conversation history from session or initialize
    conversation = request.session.get('conversation', [])

    # Add the new user message to the conversation
    conversation.append({"role": "user", "content": user_message})

    try:
        # Call the chat completion endpoint using the new syntax
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful chatbot."},
                *conversation
            ],
            max_tokens=150,
            temperature=0.7,
        )

        bot_reply = response.choices[0].message.content.strip()

        # Append assistant's reply to the conversation history
        conversation.append({"role": "assistant", "content": bot_reply})

        # Save updated conversation back to the session
        request.session['conversation'] = conversation
        request.session.modified = True

        return Response({"reply": bot_reply})

    except Exception as e:
        return Response({"error": str(e)}, status=500)
