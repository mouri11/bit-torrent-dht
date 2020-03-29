import math, bencode, hashlib, logging, os, time

class TorrentData(object):
    def __init__(self):
        self.torrent_dict = {}
        self.total_length:int = 0
        self.piece_length:int = 0
        self.pieces:int = 0
        self.info_hash:str = ''
        self.peer_id:str = ''
        self.announce_list:str = ''
        self.file_names = []
        self.no_of_pieces:int = 0

    def load_file(self,path):
        # bencode parsing
        with open(path,'rb') as torrentfile:
            parsed_data = bencode.bdecode(torrentfile.read())

        self.torrent_dict = parsed_data
        self.piece_length = self.torrent_dict['info']['piece length']
        self.pieces = self.torrent_dict['info']['pieces']
        self.info_hash = hashlib.sha1(bencode.encode(self.torrent_dict['info'])).digest()
        self.peer_id = self.generate_peer_id()
        self.announce_list = self.get_trackers()
        self.get_files()
        self.no_of_pieces = math.ceil(self.total_length / self.piece_length)
        
        # Printing out tracker list and file names
        logging.debug(self.announce_list)
        logging.debug(self.file_names)

        # Testing to check if total file length and number of files is not 0
        # assert(self.total_length > 0)
        # assert(len(self.file_names) > 0)

        return self

 
    def get_files(self):
        '''
        Finds the file names and creates the directory structure
        '''
        folder = self.torrent_dict['info']['name']

        if 'files' in self.torrent_dict['info']:
            if not os.path.exists(folder):
                os.mkdir(folder,0o0766) # setting permission for the folder

            for file in self.torrent_dict['info']['files']:
                path_name = os.path.join(folder,*file['path'])

                if not os.path.exists(os.path.dirname(path_name)):
                    os.makedirs(os.path.dirname(path_name))

                self.file_names.append({"path":path_name,"length":file['length']})
                self.total_length += file['length']

        else:
            self.file_names.append({"path":folder, "length":self.torrent_dict['info']['length']})
            self.total_length = self.torrent_dict['info']['length']


    def get_trackers(self):
        '''
        Gets the tracker URLs from the .torrent file
        '''
        if 'announce-list' in self.torrent_dict:
            return self.torrent_dict['announce-list']
        else:
            return [[self.torrent_dict['announce']]]


    def generate_peer_id(self):
        '''
        Generates a random Peer-ID with current time as seed
        '''
        seed = str(time.time())
        return hashlib.sha1(seed.encode('utf-8')).digest()

# tor = Torrent()
# tor.load_file("./sintel.torrent")
# print(tor.announce_list)
# print(tor.file_names)