File uploads
============

File uploads are **not** transported over the websocket connection, but through a different HTTP endpoint, which resides
on ``/storage/upload/`` on the current domain.

Authorization needs to be passed either as an ``Authorization: Bearer …`` header for JWTs, or as an
``Authorization: Client …`` header for client IDs.

You are expected to submit a body of type ``multipart/form-data`` with exactly one body part called ``"file"``.

You will receive one of the following responses:

* A ``403`` status code with an undefined body if the user is not allowed to upload files

* A ``400`` status code with a body of the format ``{"error": "error.code"}`` if the file can't be uploaded, with one
  of the following error codes:

  * ``file.missing``
  * ``file.type``
  * ``file.size``

* A ``201`` status code with a body of the format ``{"url": "https://…"}`` with the URL of the uploaded file.

Sample::

    > POST /storage/upload/ HTTP/1.1
    > Host: localhost:8375
    > Accept: */*
    > Authorization: Client 88a975b5-4786-4ebc-ab5d-b3ccb8a632b4
    > Content-Length: 79063
    > Content-Type: multipart/form-data; boundary=------------------------99a177b1338654ee
    >
    < HTTP/1.1 201 Created
    < Content-Type: application/json
    < Content-Length: 103
    <
    {"url": "http://localhost:8375/media/pub/sample/ba111e18-b840-48d5-befd-055a75a1a259.mbpmFRygF07a.png"}%