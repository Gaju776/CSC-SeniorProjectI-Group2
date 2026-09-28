Part 1: The Problem

Web applications serving many users cache the results of costly operations, such as database queries or rendered pages, so most requests avoid reaching the backend. Developers, operators, and users are affected when the backend is strained, since users then see slow pages or outages.

The usual method is the look-aside pattern: on a miss, the server fetches or computes the value from the source and stores it with a time-to-live (Nishtala et al., 2013).

The problem arises when a heavily requested item expires: every request arriving before the new value is stored sees a miss and recomputes it. An item read 10 times per second that takes 3 seconds to recompute causes 30 redundant recomputations, which can overload the backend and slow each recomputation further, drawing in more requests (Vattani et al., 2015). A routine expiry can thus become a cascading failure, most likely with popular keys, high traffic, and expensive recomputation.

Part 2: Evidence

As noted by Vattani et al. (2015, p. 886), the simultaneous recomputation following the expiry of a popular item can overload the backend and lead to a cascade effect. Moreover, caches that offer only simple get and set operations, for example Memcached, do not have built-in protection against stampedes (Nishtala et al. 2013, p. 388) and have provided measured production data showing that, for keys susceptible to thundering herds, the peak database query rate dropped from 17K queries per second without leases to 1.3K per second with leases, even though their definition includes a high level of both read and write activity rather than just expiry. With regard to Goodreads traffic and a one-minute recompute time, a uniform early-expiration baseline resulted in stampedes involving more than 80 and 50 processes respectively (Vattani et al., 2015, p. 892). I have neither observed nor measured any of this myself. I believe that stampedes cause outages frequently enough in typical applications for it to be significant, and that they are also important on a smaller scale, but neither of the papers makes any establishment of these points.
