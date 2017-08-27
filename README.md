# SocketIO Chat Server Code

This is the backend code I use to run a political chat service. Clients can send a request for a chat partner 
with their preferences, the server will find them a match, or, if unable to find a suitable chat partner, will 
add the client to a waiting list. Once connected, the server will join two clients in a room, provide them
with a discussion question from the database, and the clients can send messages back and forth and request new 
discussion topics. 

## Built With

* Flask - Framework used
* Redis - In-memory caching for managing connected users
* Postgresql - Database for discussion questions and blog posts
* SocketIO - real time event based communication

## Author

* **Derek Sawicki**

