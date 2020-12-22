import requests
import logging

import sys
sys.path.append('..')
from crypto_functions import CryptoFunctions

# Serialization
from cryptography.hazmat.primitives import serialization

def ask_server_parameters(server_url):

    # 1. Get the server parameters
    req = requests.get(f'{server_url}/api/parameters')

    if req.status_code != 200:
        print("The server is not available!")
        exit()

    parameters_bytes = bytes(req.json()['parameters'], 'utf-8')
    print("\nGot serialized parameters!\n", parameters_bytes)
    
    parameters = serialization.load_pem_parameters(parameters_bytes)    
    return parameters

"""
This method asks the server for the available protocols
and lets the user define the protocols to use.
It returns the cipher suite.
"""
def client_chosen_options(server_url):
    # Ask server for available protocols
    req = requests.get(f'{server_url}/api/protocols')    
    
    if req.status_code == 200:
        print("Got Protocols!")
    else:
        print("The server is not available!")
        exit()
   
    protocols = req.json()

    # Cipher choice
    while True:
        # Show options
        print("\nChoose a cipher algorithm: ")
        i=1
        for cipher in protocols['cipher']:
            print(i, ")",cipher)
            i+=1
        # Receive input
        print("> " , end =" ")
        op = int(input())
        if op >= 1 and op <= len(protocols['cipher']):
            cipher = protocols['cipher'][op-1]
            break
        print("That is not a valid option! Try again!")
    
    # Digest choice
    while True:
        # Show options
        print("\nChoose a digest: ")
        i=1
        for digest in protocols['digests']:
            print(i, ")",digest)
            i+=1
        # Receive input
        print("> " , end =" ")
        op = int(input())
        if op >= 1 and op <= len(protocols['digests']):
            cipher = protocols['digests'][op-1]
            break
        print("That is not a valid option! Try again!")

    # Cipher mode choice
    while True: 
        # Show options
        print("\nChoose a cipher mode: ")
        i=1
        for mode in protocols['cipher_mode']:
            print(i, ")",mode)
            i+=1
        # Receive input
        print("> " , end =" ")
        op = int(input())
        if op >= 1 and op <= len(protocols['cipher_mode']):
            cipher_mode = protocols['cipher_mode'][op-1]
            break
        print("That is not a valid option! Try again!")

    cipherSuite = {'cipher': cipher, 'digest': digest, 'cipher_mode':cipher_mode}
    
    return cipherSuite

"""
This method negociates the encription keys to use 
in the communications with the server.

1. GET to the server to get:
   - The server public key
2. Generate the shared key based on the server public key
3. POST to the server: 
   - The shared key generated
   - The client public key
4. As an answer to this request, the server will return:
   - His shared key
5. Compute the encription key based on:
   - The server shared key
   - The client private key
"""
def diffieHellman(server_url, private_key, public_key):
    
    # 1. Exchange public key with the server
    pk = public_key.public_bytes(
        encoding = serialization.Encoding.PEM,
        format = serialization.PublicFormat.SubjectPublicKeyInfo
    )
    print("\nSerialized public key to send server!\n", pk)
    req = requests.post(f'{server_url}/api/publickey', data={
        'public_key': pk.decode('utf-8'),
    })

    if req.status_code != 200:
        print("The server is not available!")
        exit()

    server_public_key_bytes = bytes(req.json()['public_key'], 'utf-8')
    server_public_key = serialization.load_pem_public_key(server_public_key_bytes)
    print("\nGot the server public key!\n", server_public_key)

    # 2. Generate the shared key based on the server public key
    shared_key = private_key.exchange(server_public_key)
    print("\nGenerated the client shared key!\n", shared_key)

    # 4. POST shared_key_crypto and public_key to the server
    # Convert public key to bytes
    pk = public_key.public_bytes(
        encoding = serialization.Encoding.PEM,
        format = serialization.PublicFormat.SubjectPublicKeyInfo
    )
    print("\nSerialized public key to send!\n", pk)

    data = {
        'shared_key_crypto': shared_key_crypto,
        'public_key': pk.decode('utf-8')
    }
    ans = requests.post(f'{server_url}/api/keyNegociation', data)

    if ans.status_code != 200:
        print("An error occured!\n", ans)
        exit()

    # 5. Get the server shared key from the request answer
    # TODO From here!
    print("\n4. GOT ANSWER FROM SERVER")
    print(ans)
    print(ans.json())