#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

from __future__ import division

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer
from collections import deque

class AmksTyrant(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"

        self.cap = self.up_bw
        self.upload_rates = dict()
        self.download_rates = dict()
        self.ratios = dict()
        self.unchoked = dict()
        self.diff_available = dict()
        self.last_available = dict()
        self.alpha = 0.2
        self.gamma = 0.1
        self.r = 3
    
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

        requests = [] 
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        peers.sort(key=lambda p: p.id)

        piece_directory = {}
        piece_to_peer = {}
        num_requests = {}

        for peer in peers:
            num_requests[peer.id] = 0
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            for piece_id in list(isect):
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
            for peer in piece_to_peer[piece]:
                if num_requests[peer.id] < self.max_requests:
                    start_block = self.pieces[piece]
                    r = Request(self.id, peer.id, piece, start_block)
                    requests.append(r)
                    num_requests[peer.id] += 1

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
        
        # Initialize u_j and d_j for all peers
        if round == 0:
            for peer in peers:
                self.upload_rates[peer.id] = self.up_bw / 4
                self.download_rates[peer.id] = 1
                self.unchoked[peer.id] = 0
                self.diff_available[peer.id] = 0
                self.last_available[peer.id] = 0

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:

            chosen = []
            bws = []

            # Store peers who requested pieces from you
            request_ids = []
            for request in requests:
                request_ids.append(request.requester_id)

            # Order peers by decreasing reciprocation likelihood ratio
            for peer in peers:
                self.ratios[peer.id] = self.download_rates[peer.id] / self.upload_rates[peer.id]
            # sorted_ratios = deque()
            # for key, value in sorted(self.ratios.iteritems(), key=lambda (k,v): (v,k)):
            #     sorted_ratios.appendleft(key)

            # # Unchoke until capacity is released
            # total_up = 0
            # index = 0
            # while total_up < self.cap and index < len(sorted_ratios):
            #     peer_id = sorted_ratios[index]
            #     if (total_up + self.upload_rates[peer_id]) < self.cap:
            #         if peer_id in request_ids:
            #             chosen.append(peer_id)
            #             bws.append(self.upload_rates[peer_id])
            #     index += 1
            #     total_up += self.upload_rates[peer_id]

            total_up = 0
            while total_up < self.cap:
                greatest_ratio = max(self.ratios.values())
                greatest_list = [key for key,value in self.ratios.items() if value == greatest_ratio]
                choice = random.choice(greatest_list)
                if (total_up + self.upload_rates[choice]) < self.cap:
                    if choice in request_ids:
                        chosen.append(choice)
                        bws.append(self.upload_rates[choice])
                total_up += self.upload_rates[choice]

            # Update which peers have unchoked this agent
            downloads_last = {}
            if round != 0:
                for download in history.downloads[round-1]:
                    if download.from_id not in downloads_last:
                        downloads_last[download.from_id] = download.blocks
                    else:
                        downloads_last[download.from_id] += download.blocks

                for peer in peers:
                    if peer.id in downloads_last:
                        self.unchoked[peer.id] += 1
                    else:
                        self.unchoked[peer.id] = 0

            # Update knowledge of downloads
            for peer in peers:
                self.diff_available[peer.id] = abs(len(peer.available_pieces) - self.last_available[peer.id])

            # Update u_j and d_j for all unchoked peers
            for peer in chosen:
                if round != 0:
                    if self.unchoked[peer] == 0:
                        # Update u_j if peer choked
                        self.upload_rates[peer] = self.upload_rates[peer] * (1 + self.alpha)

                        # Update d_j if peer choked
                        self.download_rates[peer] = self.diff_available[peer]
                    else:
                        # Update d_j if peer unchoked
                        self.download_rates[peer] = downloads_last[peer]

                        # Update u_j if peer unchoked for less than r periods
                        if self.unchoked[peer] < self.r:
                            self.upload_rates[peer] = self.upload_rates[peer] * (1 + self.alpha)
                        # Update u_j if peer unchoked for more than r periods
                        else:
                            self.upload_rates[peer] = self.upload_rates[peer] * (1 - self.gamma)

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        return uploads