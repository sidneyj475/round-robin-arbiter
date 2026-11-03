class ArbiterModel:
    def __init__(self, n=4):
        self.n = n
        self.next_priority = 0

    def expected_grant(self, req):
        for offset in range(self.n):
            index = (self.next_priority + offset) % self.n

            if req & (1 << index):
                return 1 << index
            
        return 0

    def update(self, grant, ready):
        if grant == 0 or not ready:
            pass
        
        else:
            granted_index = grant.bit_length() - 1
            self.next_priority = (granted_index + 1) % self.n