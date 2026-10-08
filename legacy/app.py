from flask import Flask, render_template, request, Response, jsonify
from openai import OpenAI
import json

app = Flask(__name__)

# Initialize OpenAI client
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="token-abc123"
)

# Store conversation history (in production, use a database)
conversations = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    # Initialize or get conversation history
    if session_id not in conversations:
        conversations[session_id] = [
            {"role": "system", "content": "You are Qwen, a helpful AI assistant."}
        ]
    
    # Add user message to history
    conversations[session_id].append({"role": "user", "content": user_message})
    
    def generate():
        # Get streaming response
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-1.5B-Instruct-GPTQ-Int4",
            messages=conversations[session_id],
            temperature=0.7,
            max_tokens=2048,
            stream=True
        )
        
        assistant_message = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                assistant_message += content
                # Send each chunk as SSE (Server-Sent Events)
                yield f"data: {json.dumps({'content': content})}\n\n"
        
        # Store complete assistant message
        conversations[session_id].append({"role": "assistant", "content": assistant_message})
        
        # Send completion signal
        yield f"data: {json.dumps({'done': True})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/clear', methods=['POST'])
def clear():
    data = request.json
    session_id = data.get('session_id', 'default')
    
    if session_id in conversations:
        conversations[session_id] = [
            {"role": "system", "content": "You are Qwen, a helpful AI assistant."}
        ]
    
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
