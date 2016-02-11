#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class AmksStd(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.unchoke_slots = 4

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

        piece_directory = {}
        piece_to_peer = {}
        for peer in peers:
            for piece_id in peer.available_pieces:
                if piece_id in piece_directory:
                    piece_to_peer[piece_id].append(peer)
                    piece_directory[piece_id] += 1
                else:
                    piece_to_peer[piece_id] = [peer]
                    piece_directory[piece_id] = 1

        rarest_pieces = []
        for key, value in sorted(piece_directory.iteritems(), key=lambda (k,v): (v,k)):
            rarest_pieces.append(key)

        for piece in rarest_pieces:
            print "Rare piece is " + str(piece)
            print requests
            for peer in piece_to_peer[piece]:
                if peer.num_requests < self.max_requests:
                    start_block = self.pieces[piece]
                    print "Start block is " + str(start_block)
                    r = Request(self.id, peer.id, piece, start_block)
                    requests.append(r)
                    peer.num_requests += 1

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
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

            request = random.choice(requests)
            chosen = [request.requester_id]
           
            download_speed = {}
            for peer in peers:
                download_speed[peer.id] = len(history.uploads[peer.id][round]) / history.upload_rates[peer.id]

            sorted_peers = []
            for key, value in sorted(download_speed.iteritems(), key=lambda (k,v): (v,k)):
                sorted_peers.append(key)

            # Reciprocity
            chosen = sorted_peers[:self.unchoke_slots - 1]

            # Optimistic unchoking
            chosen.append(random.choice(peers).id)

            # Evenly "split" my upload bandwidth among the one chosen requester
            bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
