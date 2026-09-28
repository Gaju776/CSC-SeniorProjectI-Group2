Part 1: The Problem

Web applications serving many users cache the results of costly operations, such as database queries or rendered pages, so most requests avoid reaching the backend. Developers, operators, and users are affected when the backend is strained, since users then see slow pages or outages.

The usual method is the look-aside pattern: on a miss, the server fetches or computes the value from the source and stores it with a time-to-live (Nishtala et al., 2013).

The problem arises when a heavily requested item expires: every request arriving before the new value is stored sees a miss and recomputes it. An item read 10 times per second that takes 3 seconds to recompute causes 30 redundant recomputations, which can overload the backend and slow each recomputation further, drawing in more requests (Vattani et al., 2015). A routine expiry can thus become a cascading failure, most likely with popular keys, high traffic, and expensive recomputation.

Part 2: Evidence

As noted by Vattani et al. (2015, p. 886), the simultaneous recomputation following the expiry of a popular item can overload the backend and lead to a cascade effect. Moreover, caches that offer only simple get and set operations, for example Memcached, do not have built-in protection against stampedes (Nishtala et al. 2013, p. 388) and have provided measured production data showing that, for keys susceptible to thundering herds, the peak database query rate dropped from 17K queries per second without leases to 1.3K per second with leases, even though their definition includes a high level of both read and write activity rather than just expiry. With regard to Goodreads traffic and a one-minute recompute time, a uniform early-expiration baseline resulted in stampedes involving more than 80 and 50 processes respectively (Vattani et al., 2015, p. 892). I have neither observed nor measured any of this myself. I believe that stampedes cause outages frequently enough in typical applications for it to be significant, and that they are also important on a smaller scale, but neither of the papers makes any establishment of these points.

Part 3: Existing Solutions #Table formatting got messed up when going from docx to md file

There are three methods for dealing with the problem: locking, leasing, and probabilistic early refresh (see Table 1).

Table 1. Existing approaches

Approach	How It Addresses the Problem	Strengths	Limitations / Questions
Cache locking (Nginx proxy_cache_lock)	One request fills a new cache item. Other requests wait (Nginx, n.d.).	It is widely used and includes only a few directives.	Waiters are delayed for a default period of up to 5 seconds before accessing the backend uncached (Nginx, n.d.). The behaviour with multiple servers is unknown.
Leases (Facebook memcache)	A client receives a token so that it can refill a missing key, while the rest wait for a short time and then try again (Nishtala et al., 2013).	The peak rate of the database dropped from 17K/s to 1.3K/s on the keys that are prone to herd behaviour (Nishtala et al., 2013).	Facebook's custom stack is part of the solution; however, clients are still waiting.
Probabilistic early expiration (XFetch)	Individual requests may be refreshed early, the likelihood increasing as the expiry date is approached (Vattani et al., 2015).	There was no need for locks or coordination, and in the tests there was no stampede larger than 8 when the recompute time was 10s.	The guarantee is probabilistic and has only been tested against a baseline of uniform delay.

Part 4: Relation to the Senior Project

The problem is at present more in line with Option 2, as it arises in the context of large-scale web applications and involves mainly the design of a system which safeguards a backend against stampedes rather than enhancing an existing tool. This is mainly a selection design since the current approaches (locking, leases, early refresh) can be compared and combined, although it might turn into an adaptive design if one of them were to be adapted for a situation it was not originally designed for, for example in the case of a cache distributed across many servers. Distributed computing is relevant because many servers make concurrent requests to a shared cache and backend and so duplicate work has to be avoided by means of coordination, and because component failure must also be taken into account: if the request that holds the lock fails, the item will remain unavailable until the lock expires (Vattani et al., 2015, p. 886).

Part 5: What I Still Do Not Know

In the first place, I have no idea how frequently stampedes result in actual outages, even though I could find out by looking through public postmortems for incidents attributed to cache expiry. Second, I don't know if Nginx's cache lock remains functional when requests are distributed among many servers; to find out, I could examine the documentation and the source code to see how the lock is stored and then carry out a test with multiple instances in a future experiment. Third, I also don't know whether lease-style protections are available outside of Facebook's own stack, something I could check by referring to the documentation for standard Memcached and Redis.

