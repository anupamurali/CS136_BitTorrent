#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging
import math

from messages import Upload, Request
from util import even_split
from peer import Peer

class AmksPropShare(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.unchoke_portion = 0.1
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            for piece_id in random.sample(isect, n):
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            if round == 0:
                # iterate through all requests and put all ids into chosen.
                chosen = [request.requester_id for request in requests]
                bws = even_split(self.up_bw, len(chosen))
            else: 
                prop_share_ids = {}
                unshared = []
                total = 0 
                prev_received = history.downloads[round-1] 
                for dl in prev_received:
                    for request in requests:
                        if dl.from_id == request.requester_id:
                            prop_share_ids[dl.from_id] = dl.blocks
                            total += dl.blocks
                requests_set = set(requests)
                chosen = prop_share_ids.keys()
                chosen_set = set(chosen)
                unshared_set = requests_set - chosen_set
                unshared = list(unshared_set)
                if len(unshared) > 0:
                    request = random.choice(unshared)
                    chosen.append(request)
                free_bw = 1.0 - self.unchoke_portion 
                bws = []
                for peer_id in prop_share_ids: 
                    bws.append(int(math.floor(self.up_bw*free_bw*prop_share_ids[peer_id]/total)))
                if math.floor(self.up_bw*free_bw) > sum(bws):
                    if len(bws) == 0:
                        bws.append(int(math.floor(self.up_bw*free_bw) - sum(bws)))
                    else:
                        bws[-1] += int(math.floor(self.up_bw*free_bw) - sum(bws))
                    if len(unshared) > 0:
                        bws.append(int(math.floor(self.up_bw-math.floor(self.up_bw*free_bw))))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
