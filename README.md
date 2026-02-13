# python-socket-whiteboard
A real-time two-player collaborative whiteboard built with Python socket programming.

## How to Use
#### 1. Start the Server
   Run the server program first. The server will display its IP address in the terminal.
#### 2. Configure Client
   Open client.py and modify the server IP address to match the IP shown by the server.
#### 3. Start Client
   Run one or two clients. Drawing actions between connected clients will be synchronized in real-time.

## Function Description
#### Undo
- Undo only reverts your own last drawing action
- It does NOT undo the other client’s drawing
#### Clear
- Clear will reset the canvas for both clients
- Only the client who pressed Clear can undo the clear action
#### Rejoin Behavior
- If a client disconnects and reconnects:
-- It will synchronize to the current canvas state
- If no clients are connected:
-- The canvas state will rese

## Server Behavior
- The server displays the IP address of connected clients
