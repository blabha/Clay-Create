import time

class SessionState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.started          = False
        self.cols             = 3
        self.rows             = 3
        self.participants     = 4
        self.blocks           = []
        self.participant_list = []
        self.history          = []
        self.active_block     = None
        self.last_done        = None
        self._projection      = None

    def start(self, cols, rows, participants):
        self.reset()
        self.started      = True
        self.cols         = cols
        self.rows         = rows
        self.participants = participants
        total = cols * rows
        self.blocks = [
            {
                'index':      i,
                'name':       f'Block {i+1}',
                'status':     'pending',
                'sculptor':   None,
                'edges':      self._get_edge_conditions(i, cols, rows),
                'start_time': None,
                'end_time':   None,
            }
            for i in range(total)
        ]
        self.blocks[0]['status'] = 'available'

    def assign_block(self, block_idx, name):
        if self.active_block is not None:
            return {'success': False, 'error': 'Another block is already active'}
        if block_idx < 0 or block_idx >= len(self.blocks):
            return {'success': False, 'error': 'Invalid block index'}
        block = self.blocks[block_idx]
        if block['status'] != 'available':
            return {'success': False, 'error': f"Block is not available (status: {block['status']})"}
        self._clear_available()
        block['status']     = 'sculpting'
        block['sculptor']   = name
        block['start_time'] = time.time()
        self.active_block   = block_idx
        self._mark_neighbor_edges(block_idx)
        self.participant_list.append({
            'name':        name,
            'block_index': block_idx,
            'status':      'sculpting',
        })
        return {'success': True}

    def complete_block(self, block_idx):
        if block_idx != self.active_block:
            return {'success': False, 'error': 'Block is not active'}
        block = self.blocks[block_idx]
        block['status']   = 'done'
        block['end_time'] = time.time()
        elapsed = int(block['end_time'] - (block['start_time'] or block['end_time']))
        m, s = divmod(elapsed, 60)
        self.history.insert(0, {
            'block_name': block['name'],
            'sculptor':   block['sculptor'],
            'time':       f"{m:02d}:{s:02d}",
        })
        part = next(
            (p for p in self.participant_list
             if p['block_index'] == block_idx and p['status'] == 'sculpting'),
            None
        )
        if part:
            part['status'] = 'done'
        self.active_block = None
        self.last_done    = block_idx
        used_fallback = self._compute_available(block_idx)
        return {'success': True, 'used_fallback': used_fallback}

    def reset_block(self, block_idx):
        if block_idx != self.active_block:
            return {'success': False, 'error': 'Block is not active'}
        block = self.blocks[block_idx]
        block['status']     = 'available'
        block['sculptor']   = None
        block['start_time'] = None
        self.participant_list = [
            p for p in self.participant_list
            if not (p['block_index'] == block_idx and p['status'] == 'sculpting')
        ]
        self.active_block = None
        if self.last_done is not None:
            self._compute_available(self.last_done)
        return {'success': True}

    def _clear_available(self):
        for b in self.blocks:
            if b['status'] == 'available':
                b['status'] = 'pending'

    def _compute_available(self, last_idx):
        self._clear_available()
        self._unlock_neighbors_of(last_idx)
        has_avail = any(b['status'] == 'available' for b in self.blocks)
        if not has_avail:
            for i, b in enumerate(self.blocks):
                if b['status'] == 'done':
                    self._unlock_neighbors_of(i)
            return True
        return False

    def _unlock_neighbors_of(self, idx):
        col = idx % self.cols
        row = idx // self.cols
        for ni in [
            (row - 1) * self.cols + col,
            (row + 1) * self.cols + col,
            row * self.cols + (col - 1),
            row * self.cols + (col + 1),
        ]:
            if 0 <= ni < len(self.blocks):
                n_col = ni % self.cols
                n_row = ni // self.cols
                if abs(n_col - col) + abs(n_row - row) == 1:
                    if self.blocks[ni]['status'] == 'pending':
                        self.blocks[ni]['status'] = 'available'

    def _mark_neighbor_edges(self, idx):
        col = idx % self.cols
        row = idx // self.cols
        for ni, side in [
            ((row - 1) * self.cols + col, 'bottom'),
            ((row + 1) * self.cols + col, 'top'),
            (row * self.cols + (col - 1), 'right'),
            (row * self.cols + (col + 1), 'left'),
        ]:
            if 0 <= ni < len(self.blocks):
                if self.blocks[ni]['edges'][side] is None:
                    self.blocks[ni]['edges'][side] = 'conditioned'

    def _get_edge_conditions(self, idx, cols, rows):
        col = idx % cols
        row = idx // cols
        return {
            'top':    'free' if row == 0        else None,
            'bottom': 'free' if row == rows - 1 else None,
            'left':   'free' if col == 0        else None,
            'right':  'free' if col == cols - 1 else None,
        }

    def is_reuse_mode(self):
        unique_names = set(p['name'] for p in self.participant_list)
        return len(unique_names) >= self.participants

    def unique_participant_names(self):
        seen = set()
        names = []
        for p in self.participant_list:
            if p['name'] not in seen:
                seen.add(p['name'])
                names.append(p['name'])
        return names

    def set_projection(self, elements, curves, meta=None):
        self._projection = {'elements': elements, 'curves': curves, 'meta': meta or {}}

    def get_projection(self):
        return self._projection

    def set_scan(self, block_idx, data):
        pass

    def to_dict(self):
        completed = sum(1 for b in self.blocks if b['status'] == 'done')
        total     = len(self.blocks)
        return {
            'started':             self.started,
            'cols':                self.cols,
            'rows':                self.rows,
            'participants':        self.participants,
            'blocks':              self.blocks,
            'participant_list':    self.participant_list,
            'history':             self.history,
            'active_block':        self.active_block,
            'last_done':           self.last_done,
            'completed':           completed,
            'total':               total,
            'progress':            round(completed / total * 100) if total > 0 else 0,
            'is_reuse_mode':       self.is_reuse_mode(),
            'unique_participants': self.unique_participant_names(),
        }
