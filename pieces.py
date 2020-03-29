import hashlib, math, time, logging

from pubsub import pub # creates a publisher-subscriber module for messaging

from block import Blocks,BLOCK_SIZE, Block_State

class DataPieces(object):
    def __init__(self, piece_index:int, piece_size:int, piece_hash:str):
        self.piece_index:int = piece_index
        self.piece_size:int = piece_size
        self.piece_hash:str = piece_hash
        self.is_full:bool = False
        self.files = []
        self.raw_data:bytes = b''
        self.no_of_blocks:int = int(math.ceil(float(piece_size) / BLOCK_SIZE))
        self.blocks:list[Blocks] = []

        self._alloc_blocks();

    def _alloc_blocks(self):
        self.blocks = []

        if self.no_of_blocks > 1:
            for i in range(self.no_of_blocks):
                self.blocks.append(Blocks())

            # last block may not be divisible by BLOCK_SIZE
            if (self.piece_size % BLOCK_SIZE > 0):
                self.blocks[self.no_of_blocks - 1].block_size = self.piece_size % BLOCK_SIZE

        else:
            self.blocks.append(Blocks(block_size = int(self.piece_size))) # only one block in file

    def _save_piece(self): # writes file pieces to disk
        for file in self.files:
            path_file = file["path"]
            file_offset = file["fileOffset"]
            piece_offset = file["pieceOffset"]
            length = file["length"]

            try:
                f = open(path_file, 'r+b')  # Already existing file
            except IOError:
                f = open(path_file, 'wb')  # New file
            except Exception:
                logging.exception("Can't write to file")
                return

            f.seek(file_offset)
            f.write(self.raw_data[piece_offset:piece_offset + length])
            f.close()

    def _merge_blocks(self):
        torr_buf = b''

        for block in self.blocks:
            torr_buf += block.data

        return torr_buf

    def _valid_blocks(self, piece_raw_data):
        hashed_piece_raw_data = hashlib.sha1(piece_raw_data).digest()

        if hashed_piece_raw_data == self.piece_hash:
            return True

        logging.warning("Error Piece Hash")
        logging.debug("{} : {}".format(hashed_piece_raw_data, self.piece_hash))
        return False

    def set_to_full(self):
        data = self._merge_blocks() # merging all pieces

        if not self._valid_blocks(data): # matching hashes of all pieces against torrent file hash
            self._alloc_blocks()
            return False

        self.is_full = True
        self.raw_data = data
        self._save_piece()
        pub.sendMessage('PiecesMgr.PieceCompleted', piece_index=self.piece_index)

        return True

    def update_block_status(self):
        for i,block in enumerate(self.blocks):
            if block.state == Block_State.PENDING and (time.time() - block.last_seen) > 5:
                self.blocks[i] = Blocks() # free block if status is pending for 5s

    def set_block(self,offset,data):
        index = int(offset / BLOCK_SIZE)

        if not self.is_full and not self.blocks[index].state == Block_State.FULL:
            self.blocks[index].data = data
            self.blocks[index].state = Block_State.FULL

    def get_empty_block(self):
        if self.is_full:
            return None

        for block_index, block in enumerate(self.blocks):
            if block.state == Block_State.FREE:
                self.blocks[block_index].state = Block_State.PENDING
                self.blocks[block_index].last_seen = time.time()
                return self.piece_index, block_index * BLOCK_SIZE, block.block_size

        return None

    def are_blocks_full(self):
        for block in self.blocks:
            if block.state == Block_State.FREE or block.state == Block_State.PENDING:
                return False

        return True