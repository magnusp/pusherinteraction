# pusherinteraction
Twisted interaction with Pusher

### Prerequisites
pip install -r requirements.txt

### Running
Expose the following environment variables
- PUSHER_KEY
- PUSHER_SECRET
- PUSHER_APPID

Invoke <pre>python pusherinteraction.py</pre>

Telnet to port 8023 on probably any interface. The telnet interface responds to the following lines and interacts
accordingly with Pusher:

* sub
    * Subscribes to the private channel 'pusherinteraction'.
* pub
    * Publishes a message to 'pusherinteraction'.
* disco
    * Disconnects the websocket client.

The interaction can be observed in the Pusher debug panel.