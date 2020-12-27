#!/usr/bin/env python
from twisted.web import server, resource
from twisted.internet import reactor, defer
import logging
import binascii
import json
import os
import math
import uuid

# Serialization
from cryptography.hazmat.primitives import serialization

# Diffie-hellman
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import sys
sys.path.append('..')

from crypto_functions import CryptoFunctions
from licenses import *

logger = logging.getLogger('root')
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
logging.basicConfig(format=FORMAT)
logger.setLevel(logging.DEBUG)

CATALOG = { '898a08080d1840793122b7e118b27a95d117ebce': 
            {
                'name': 'Sunny Afternoon - Upbeat Ukulele Background Music',
                'album': 'Upbeat Ukulele Background Music',
                'description': 'Nicolai Heidlas Music: http://soundcloud.com/nicolai-heidlas',
                'duration': 3*60+33,
                'file_name': '898a08080d1840793122b7e118b27a95d117ebce.mp3',
                'file_size': 3407202
            }
        }

CATALOG_BASE = 'catalog'
CHUNK_SIZE = 1024 * 4  #block

class MediaServer(resource.Resource):
    isLeaf = True

    # Constructor
    def __init__(self):
        print("Initializing server...")
        # TODO Change on production to new parameters every initialization! 
        # self.parameters = dh.generate_parameters(generator=2, key_size=2048)
        with open('parameters', 'rb') as f:
            self.parameters = serialization.load_pem_parameters(f.read().strip())    
            print("Loaded parameters!")
        # Create the private/public keys pairs
        self.shared_key = None

        self.CIPHER = None
        self.DIGEST = None
        self.CIPHER_MODE= None
        self.KEY = None
        self.sessions = {}

    # Send the server public key
    def do_parameters(self, request):
        request.responseHeaders.addRawHeader(b"content-type", b"application/json")
        # Convert parameters to bytes
        pr = self.parameters.parameter_bytes(
            encoding = serialization.Encoding.PEM,
            format = serialization.ParameterFormat.PKCS3
        )
        print("\nSerialized parameters as bytes to answer request!\n", pr)

        # Return it
        return json.dumps({
            'parameters': pr.decode('utf-8')
        }).encode('latin')

    # Send the list of available protocols
    def do_choose_protocols(self, request):
        protocols = {
            'cipher': ['AES','3DEs'], 
            'digests': ['SHA512', 'BLAKE2'], 
            'cipher_mode': ['CBC', 'OFB']  
        }
        
        request.responseHeaders.addRawHeader(b"content-type", b"application/json")
        return json.dumps(protocols).encode('latin')


    # Send the list of media files to clients
    def do_list(self, request):

        #auth = request.getHeader('Authorization')
        #if not auth:
        #    request.setResponseCode(401)
        #    return 'Not authorized'

        # Build list
        media_list = []
        for media_id in CATALOG:
            media = CATALOG[media_id]
            media_list.append({
                'id': media_id,
                'name': media['name'],
                'description': media['description'],
                'chunks': math.ceil(media['file_size'] / CHUNK_SIZE),
                'duration': media['duration']
                })

        # Return list to client
        request.responseHeaders.addRawHeader(b"content-type", b"application/json")
        message = json.dumps(media_list).encode()
        return self.cipher(request, message)


    # Send a media chunk to the client
    def do_download(self, request):
        logger.debug(f'Download: args: {request.args}')
        
        media_id = request.args.get(b'id', [None])[0]
        logger.debug(f'Download: id: {media_id}')

        # Check if the media_id is not None as it is required
        if media_id is None:
            request.setResponseCode(400)
            request.responseHeaders.addRawHeader(b"content-type", b"application/json")
            message = json.dumps({'error': 'invalid media id'}).encode()
            return self.cipher(request, message, bytes(chunk_id))
        
        # Convert bytes to str
        media_id = media_id.decode('latin')

        # Search media_id in the catalog
        if media_id not in CATALOG:
            request.setResponseCode(404)
            request.responseHeaders.addRawHeader(b"content-type", b"application/json")
            message = json.dumps({'error': 'media file not found'}).encode()
            return self.cipher(request, message, bytes(chunk_id))
        
        # Get the media item
        media_item = CATALOG[media_id]

        # Check if a chunk is valid
        chunk_id = request.args.get(b'chunk', [b'0'])[0]
        valid_chunk = False
        try:
            chunk_id = int(chunk_id.decode('latin'))
            if chunk_id >= 0 and chunk_id  < math.ceil(media_item['file_size'] / CHUNK_SIZE):
                valid_chunk = True
                #if is valid chunck update_license
                media_duration= media_item['duration']
                
                update_license(self.username,media_duration)
        except:
            logger.warn("Chunk format is invalid")

        if not valid_chunk:
            request.setResponseCode(400)
            request.responseHeaders.addRawHeader(b"content-type", b"application/json")
            message = json.dumps({'error': 'invalid chunk id'}).encode()
            return self.cipher(request, message, bytes(chunk_id))
            
        logger.debug(f'Download: chunk: {chunk_id}')

        offset = chunk_id * CHUNK_SIZE

        # Open file, seek to correct position and return the chunk
        with open(os.path.join(CATALOG_BASE, media_item['file_name']), 'rb') as f:
            f.seek(offset)
            data = f.read(CHUNK_SIZE)

            request.responseHeaders.addRawHeader(b"content-type", b"application/json")
            message = json.dumps(
                {
                    'media_id': media_id, 
                    'chunk': chunk_id, 
                    'data': binascii.b2a_base64(data).decode('latin').strip()
                }
            ).encode()
            return self.cipher(request, message, bytes(chunk_id))

        # File was not open?
        request.responseHeaders.addRawHeader(b"content-type", b"application/json")
        message = json.dumps({'error': 'unknown'}).encode()
        return self.cipher(request, message, bytes(chunk_id))

    # Handle a GET request
    def render_GET(self, request):
        logger.debug(f'\nReceived request for {request.uri}')

        try:
            if request.path == b'/api/parameters':
                return self.do_parameters(request)
            elif request.path == b'/api/protocols':
                return self.do_choose_protocols(request)
            #elif request.uri == 'api/key':
            #...
            #elif request.uri == 'api/auth':

            elif request.path == b'/api/list':
                return self.do_list(request)

            elif request.path == b'/api/download':
                print("OK")
                return self.do_download(request)
                
       
            

            else:
                request.responseHeaders.addRawHeader(b"content-type", b'text/plain')
                return b'Methods: /api/protocols /api/list /api/download'

        except Exception as e:
            logger.exception(e)
            request.setResponseCode(500)
            request.responseHeaders.addRawHeader(b"content-type", b"text/plain")
            return b''
        
    """
    This method allows the client to register at the server (send his public key)
    The server generates a key pair for that client and a shared key based on those
    It also generates a session id for client
    Answers to client the server public key and the session id
    """
    def do_public_key(self, request):
        data = request.args
        if data == None or data == '':
            print('Data is none or empty')
            return 
        print(request.args) 

        # 1. Get the client public key
        print("\nClient public key raw.\n", request.args[b'public_key'][0])
        client_public_key = serialization.load_pem_public_key(request.args[b'public_key'][0])
        print("\nGot the client public key!\n", client_public_key)

        # 2. Generate a session id for client
        sessionid = uuid.uuid1()
        print("\nGenerated session id for client:", sessionid)

        # 3. Generate key pair for client
        private_key, public_key = CryptoFunctions.newKeys(self.parameters)
        print("\nPrivate key created!\n", private_key)
        print(private_key.private_bytes(
            encoding = serialization.Encoding.PEM,
            format = serialization.PrivateFormat.PKCS8,
            encryption_algorithm = serialization.NoEncryption()
        ))
        print("\nPublic key generated!\n", public_key)
        print(public_key.public_bytes(
            encoding = serialization.Encoding.PEM,
            format = serialization.PublicFormat.SubjectPublicKeyInfo
        ))

        # 4. Diffie-Hellman | Generate shared key
        shared_key = private_key.exchange(client_public_key)
        print("\nGenerated the shared key for client!\n", shared_key)

        # 5. Convert public key to bytes
        pk = public_key.public_bytes(
            encoding = serialization.Encoding.PEM,
            format = serialization.PublicFormat.SubjectPublicKeyInfo
        )
        print("\nSerialized public key to answer request!\n", pk)

        # 6. Register client session
        self.sessions[sessionid] = {
            'public_key': public_key,
            'private_key': private_key,
            'shared_key': shared_key
        }

        # 7. Return public key to client
        request.responseHeaders.addRawHeader(b"sessionid", sessionid.bytes)
        return json.dumps({
            'public_key': pk.decode('utf-8'),
        }).encode('latin')
    
    def process_negotiation(self,request):
        data = request.args
        
        if data == None or data == '':
            print('Data is none or empty')
        else:
            self.CIPHER = request.args[b'cipher'][0].decode('utf-8')
            self.DIGEST = request.args[b'digest'][0].decode('utf-8')
            self.CIPHER_MODE = request.args[b'cipher_mode'][0].decode('utf-8')
            print(f"\n\nDefined chiper suite as:\nCipher: {self.CIPHER}\nDigest: {self.DIGEST}\nMode: {self.CIPHER_MODE}\n")
    
    #login and create new license
    
    def new_license(self, request):
        data = request.args
        username, password = ""
        if data == None or data == '':
            print('Data is none or empty')
        else:
            self.username  = request.args[b'username'][0].decode('utf-8')
            password = request.args[b'passowrd'][0].decode('utf-8')
        add_new_license( self.username,password)
   
    """
    #logout and update license
    def update_license(self, request):
        data = request.args
        if data == None or data == '':
            print('Data is none or empty')
        else:
            self.USERNAME = request.args[b'username'][0].decode('utf-8')
    """    

    # Handle a POST request
    def render_POST(self, request):
        logger.debug(f'\nReceived POST for {request.uri}')
        try:
            if request.path == b'/api/suite':
                return self.process_negotiation(request)
            elif request.path == b'/api/publickey':
                return self.do_public_key(request)
            elif request.path == b'/api/newLicense':
                return self.new_license(request)

          
        
        except Exception as e:
            logger.exception(e)
            request.setResponseCode(501)
            request.responseHeaders.addRawHeader(b"content-type", b"text/plain")
            return b''

    # Cipher
    def cipher(self, request, response, append=None):
        """
        This method ciphers a response to a request
        It also generates a MIC for the cryptogram
        --- Parameters
        append      Bytes to append to shared_key before ciphering
        """
        cryptogram = CryptoFunctions.symetric_encryption(
            key = self.shared_key if not append else self.shared_key + append,
            message = response,
            algorithm_name = self.CIPHER,
            cypher_mode = self.CIPHER_MODE,
            digest_mode = self.DIGEST,
            encode = True
        )

        MIC = CryptoFunctions.create_digest(cryptogram, self.DIGEST)
        print("Generated MIC:\n",MIC)
        request.responseHeaders.addRawHeader(b"MIC", MIC)
        print(request.responseHeaders)

        return cryptogram


print("Server started")
print("URL is: http://IP:8080")

s = server.Site(MediaServer())
reactor.listenTCP(8080, s)
reactor.run()