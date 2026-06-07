
<style>
  
  .chat-btn {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 50%;
    width: 60px;
    height: 60px;
    font-size: 24px;
    cursor: pointer;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    z-index: 9999;
  }

  
  .chat-window {
    display: none; 
    position: fixed;
    bottom: 90px;
    right: 20px;
    width: 300px;
    height: 400px;
    background-color: white;
    border-radius: 10px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    z-index: 9999;
    flex-direction: column;
    overflow: hidden;
  }

  .chat-header {
    background-color: #007bff;
    color: white;
    padding: 15px;
    font-weight: bold;
    display: flex;
    justify-content: space-between;
  }

  .chat-header span { cursor: pointer; }

  .chat-body {
    flex-grow: 1;
    padding: 15px;
    overflow-y: auto;
    background-color: #f9f9f9;
  }

  .chat-footer {
    display: flex;
    padding: 10px;
    border-top: 1px solid #ddd;
  }

  .chat-footer input {
    flex-grow: 1;
    padding: 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
  }

  .chat-footer button {
    background-color: #007bff;
    color: white;
    border: none;
    margin-left: 5px;
    padding: 8px 15px;
    border-radius: 4px;
    cursor: pointer;
  }
</style>


<button class="chat-btn" id="chatBtn">💬</button>


<div class="chat-window" id="chatWindow">
  <div class="chat-header">
    Need Help?
    <span id="closeChat">✖</span>
  </div>
  <div class="chat-body" id="chatBody">
    <p><strong>Bot:</strong> Hi! How can I help you today?</p>
  </div>
  <div class="chat-footer">
    <input type="text" id="chatInput" placeholder="Type a message...">
    <button id="sendBtn">Send</button>
  </div>
</div>

<script>
  
  const chatBtn = document.getElementById('chatBtn');
  const chatWindow = document.getElementById('chatWindow');
  const closeChat = document.getElementById('closeChat');

  
  chatBtn.addEventListener('click', () => {
    if (chatWindow.style.display === 'flex') {
      chatWindow.style.display = 'none';
    } else {
      chatWindow.style.display = 'flex';
    }
  });

  
  closeChat.addEventListener('click', () => {
    chatWindow.style.display = 'none';
  });
</script>


