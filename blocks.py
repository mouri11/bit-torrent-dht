from enum import enum

BLOCK_SIZE = 2 ** 14

class Block_State(Enum):
    FREE = 0
    PENDING = 1
    FULL = 2

class Blocks():
    def __init__(self, state: Block_State = FREE, block_size:int = BLOCK_SIZE, 
                 data: bytes = b'',last_seen:float = 0):
        self.state: Block_State = state
        self.block_size:int = block_size
        self.data:bytes = data
        self.last_seen:float = last_seen

    def __str__(self):
        return '%s - %d - %d - %d' %(self.state, self.block_size, len(self.data), self.last_seen)
