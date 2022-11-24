"""
# Training a Chess Endgame Network

For this tutorial, we're going to attempt to train a Neural Network to classify 
[chess endgame](https://en.wikipedia.org/wiki/Chess_endgame) positions as either 
win, draw or loss. 

## Background and motivation

You don't need to read this section to follow along with the rest of the example, 
but you might find it interesting!

Lots of work has been done over the years to create GOFAI chess-playing software
(called engines). These almost always work by traversing the game-tree from the 
current position, and applying a relatively simple algorithm like [minimax](https://en.wikipedia.org/wiki/Minimax).
This requires being able to statically determine a heuristic evaluation of how 
favourable a position is at each of the leaf nodes in the game tree. In the first
few decades of chess programming, strong human players would have a lot of input
into this 'evaluation function'. Standard heuristics incorporated into the 
evaluation function would be things like developing pieces onto good 
squares, controlling the center of the board and ensuring the safety of one's 
own king.

In recent years, chess programmers have moved away from directly incorporating 
centuries of human chess wisdom into these hand-written evaluation functions and 
have instead trained neural networks to consume a board position and spit out an
evaluation of it. By far the strongest engine of the last several years, 
[Stockfish](https://en.wikipedia.org/wiki/Stockfish_(chess)) has used this 
approach since 2020. The evaluation function is now a neural network, which was 
trained on a dataset of positions that had been evaluated with an earlier 
version of Stockfish searching to a relatively high depth. 

If you're interested in learning more about chess programming, the website 
[chessprogramming.org](https://www.chessprogramming.org/Main_Page) is packed with 
great content!

## Approach 

For this example, we want to try a very simple idea inspired by the Stockfish 
approach described above. 

Since we're starting from scratch, we don't have a dataset derived from an earlier
version of our (as yet non-existent) program, so we need something else. As it 
happens, there is a dataset available of chess endgame positions (meaning 
positions from late in the game, when there are only a small number of pieces left
on the board) which is completely exhaustive and is known to be 100% accurate 
ground truth. The dataset is called [Syzygy](https://www.chessprogramming.org/Syzygy_Bases)
and the version with every possible position up to 5 chessmen is just under 1GB 
in size. Let's use that.



"""
