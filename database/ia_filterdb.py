import logging
from struct import pack
import re
import base64
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import * # DATABASE_URI, DATABASE_NAME, COLLECTION_NAME, MAX_BTN
from pymongo import MongoClient


# First Database For File Saving 
client = MongoClient(FILE_DB_URI)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]

# Second Database For File Saving
sec_client = MongoClient(SEC_FILE_DB_URI)
sec_db = sec_client[DATABASE_NAME]
sec_col = sec_db[COLLECTION_NAME]

client = AsyncIOMotorClient(DATABASE_URI)
mydb = client[DATABASE_NAME]
instance = Instance.from_db(mydb)

        
async def save_file(media):
    """Save file in the database with duplicate protection and dual DB support."""

    file_id, file_ref = unpack_new_file_id(media.file_id)
    file_name = clean_file_name(media.file_name)

    file = {
        'file_id': file_id,
        'file_ref': file_ref,
        'file_name': file_name,
        'file_size': media.file_size,
        'caption': media.caption.html if media.caption else None,
        'mime_type': getattr(media, 'mime_type', None),
        'file_type': getattr(media, 'mime_type', None).split("/")[0] if media.mime_type else None
    }

    # First check if already exists in primary DB
    if col.find_one({'file_id': file_id, 'file_name': file_name}):
        print(f"{file_name} already exists in primary DB.")
        return False, 0

    try:
        col.insert_one(file)
        print(f"{file_name} successfully saved in primary DB.")
        return True, 1
    except Exception as e:
        print(f"Primary DB insert failed: {e}")
        if MULTIPLE_DATABASE:
            # Check if already exists in secondary DB
            if sec_col.find_one({'file_id': file_id, 'file_name': file_name}):
                print(f"{file_name} already exists in secondary DB.")
                return False, 0
            try:
                sec_col.insert_one(file)
                print(f"{file_name} successfully saved in secondary DB.")
                return True, 1
            except Exception as e2:
                print(f"Secondary DB insert failed: {e2}")
                return False, 0
        else:
            print("Primary DB full. Enable MULTIPLE_DATABASE to use secondary DB.")
            return False, 0

            
async def get_files_db_size():
    return (await mydb.command("dbstats"))['dataSize']
    
async def save_file(media):
    """Save file in database"""

    # TODO: Find better way to get same file_id for same media to avoid duplicates
    file_id, file_ref = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
    try:
        file = Media(
            file_id=file_id,
            file_ref=file_ref,
            file_name=file_name,
            file_size=media.file_size,
            mime_type=media.mime_type,
            caption=media.caption.html if media.caption else None,
            file_type=media.mime_type.split('/')[0]
        )
    except ValidationError:
        print('Error occurred while saving file in database')
        return 'err'
    else:
        try:
            await file.commit()
        except DuplicateKeyError:      
            print(f'{getattr(media, "file_name", "NO_FILE")} is already saved in database') 
            return 'dup'
        else:
            print(f'{getattr(media, "file_name", "NO_FILE")} is saved to database')
            return 'suc'

def clean_file_name(file_name):
    """Clean and format the file name."""
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(file_name)) 
    unwanted_chars = ['[', ']', '(', ')', '{', '}']
    
    for char in unwanted_chars:
        file_name = file_name.replace(char, '')
        
    return ' '.join(filter(lambda x: not x.startswith('@') and not x.startswith('http') and not x.startswith('www.') and not x.startswith('t.me'), file_name.split()))

def is_file_already_saved(file_id, file_name):
    """Check if the file is already saved in either collection."""
    found1 = {'file_name': file_name}
    found = {'file_id': file_id}

    for collection in [col, sec_col]:
        if collection.find_one(found1) or collection.find_one(found):
            print(f"{file_name} is already saved.")
            return True
            
    return False

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """For given query return (results, next_offset)"""
    
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]') 
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        regex = query
    filter = {'file_name': regex}
    files = []
    if MULTIPLE_DATABASE:
        cursor1 = col.find(filter).sort('$natural', -1).skip(offset).limit(max_results)
        cursor2 = sec_col.find(filter).sort('$natural', -1).skip(offset).limit(max_results)
        
        for file in cursor1:
            files.append(file)
        for file in cursor2:
            files.append(file)
    else:
        cursor = col.find(filter).sort('$natural', -1).skip(offset).limit(max_results)
        
        for file in cursor:
            files.append(file)

    total_results = col.count_documents(filter) if not MULTIPLE_DATABASE else (col.count_documents(filter) + sec_col.count_documents(filter))
    next_offset = "" if (offset + max_results) >= total_results else (offset + max_results)

    return files, next_offset, total_results
    
async def get_bad_files(query, file_type=None, offset=0, filter=False):
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return []
    filter = {'file_name': regex}
    if file_type:
        filter['file_type'] = file_type
    total_results = await Media.count_documents(filter)
    cursor = Media.find(filter)
    cursor.sort('$natural', -1)
    files = await cursor.to_list(length=total_results)
    return files, total_results
    
async def get_file_details(query):
    filter = {'file_id': query}
    cursor = Media.find(filter)
    filedetails = await cursor.to_list(length=1)
    return filedetails

def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    """Return file_id, file_ref"""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref
    
