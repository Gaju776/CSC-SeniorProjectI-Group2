Part 1: The Problem

Web applications serving many users cache the results of costly operations, such as database queries or rendered pages, so most requests avoid reaching the backend. Developers, operators, and users are affected when the backend is strained, since users then see slow pages or outages.

The usual method is the look-aside pattern: on a miss, the server fetches or computes the value from the source and stores it with a time-to-live (Nishtala et al., 2013).

The problem arises when a heavily requested item expires: every request arriving before the new value is stored sees a miss and recomputes it. An item read 10 times per second that takes 3 seconds to recompute causes 30 redundant recomputations, which can overload the backend and slow each recomputation further, drawing in more requests (Vattani et al., 2015). A routine expiry can thus become a cascading failure, most likely with popular keys, high traffic, and expensive recomputation.
