# Route agreement: a sheaf whose maps carry the accounting

Draft, 14 November 2026. Code: `route_agreement.py`. Tests: `tests/test_route_agreement.py`. Models: `models/`.

## 1. Why a second construction

The H¹ linter in this repository uses restriction maps that only select shared field names. Its sheaf therefore splits into one constant piece per field, and its H¹ is a count of loops in each field's support graph (see `REVIEW_CHANGES.md`). That number does not change when a protocol's accounting changes.

Here the maps say *how* each quantity is computed across a transition. The cohomology then depends on the protocol's arithmetic, and its global sections have a direct meaning.

## 2. Setting

Let G be a finite directed graph of states and transitions. Self-loops and parallel transitions are allowed. Fix an initial state r, and assume every state can be reached from r by a directed route.

For each state v let V_v be a finite-dimensional vector space over ℚ: the quantities the protocol **promises are determined by the state alone** (for example, at SETTLED: the provider's payout, the platform fee, what is left in escrow). For each transition e from u to v let T_e : V_u → V_v be linear: the accounting the transition performs.

Define a cellular sheaf F on G by F(v) = V_v and F(e) = V_v for e : u → v, with restriction maps T_e (from the tail u) and the identity (from the head v). Its coboundary is

    (δx)_e = T_e x_u − x_v        for e : u → v,

and H⁰(G; F) = ker δ is the space of assignments x with x_v = T_e x_u on every transition.

For a directed route p = e_1 … e_k write T_p = T_{e_k} ∘ … ∘ T_{e_1}. The empty route at r has T = id.

## 3. Results

**Theorem 1 (route agreement).** Evaluation at the initial state, x ↦ x_r, is an injective linear map H⁰(G; F) → V_r whose image is the *agreement subspace*

    A = { a ∈ V_r : T_p a = T_q a for all directed routes p, q from r with the same end state }.

*Proof.* Let x ∈ H⁰. By induction on the length of a route p from r to v, x_v = T_p x_r. So x is determined by x_r (every state is reachable), which gives injectivity, and for two routes p, q ending at the same v we get T_p x_r = x_v = T_q x_r, so x_r ∈ A. Conversely let a ∈ A, and set x_v = T_p a for any route p from r to v; this does not depend on p because a ∈ A. For a transition e : u → v and a route p from r to u, the route p·e ends at v, so x_v = T_e T_p a = T_e x_u. Hence x ∈ H⁰ and x_r = a. ∎

**Corollary 2.** dim H⁰ = dim V_r if and only if every two routes from r to the same state agree on every promised quantity, for every initial value. In general dim V_r − dim H⁰ is the number of independent directions of initial values on which some pair of routes disagrees.

The condition in Theorem 1 ranges over infinitely many pairs of routes when G has directed cycles. It reduces to one condition per independent loop:

**Proposition 3 (localisation).** Let τ be a spanning arborescence rooted at r, and τ(v) its route from r to v. Then

    A = ⋂ over transitions e : u → v not in τ of   ker( T_e T_{τ(u)} − T_{τ(v)} ).

*Proof.* Each condition on the right compares two routes ending at v, so A is contained in the intersection. Conversely let a lie in the intersection and set x_v = T_{τ(v)} a. A tree transition e : u → v has τ(v) = τ(u)·e, so x_v = T_e x_u; a non-tree transition satisfies x_v = T_e x_u by assumption. So x ∈ H⁰ with x_r = a, and a ∈ A by Theorem 1. ∎

Each non-tree transition whose difference D_e = T_e T_{τ(u)} − T_{τ(v)} is non-zero names two concrete routes and the quantities (the non-zero rows of D_e) on which they differ. The tool prints exactly this.

**Corollary 4 (what H¹ is here).** By rank and nullity,

    dim H¹ = Σ over e not in τ of dim V_{head(e)}  −  (dim V_r − dim H⁰).

So H¹ is largest when all routes agree and shrinks by one for each direction of disagreement. In this construction the informative group is H⁰, as in the sheaf treatments of contextuality and of distributed tasks, where the object of interest is the existence of global sections.

**Definition 5 (views).** A participant's view at a state is a set of quantities it can observe. A disagreement D_e is *visible* to a participant if a row of D_e belonging to one of its quantities is non-zero, and invisible otherwise. A disagreement invisible to both trading parties is one that neither has a reason to report.

**What is checked by machine.** `tests/test_route_agreement.py` computes dim H⁰ twice on 600 random models, once as the kernel of the coboundary matrix and once from Proposition 3, and requires equality. The models include non-invertible maps, zero-dimensional stalks, self-loops and back edges; both agreeing and disagreeing outcomes occur. Removing self-loops from the loop set turns that test red. All arithmetic is exact.

## 4. Is this true by construction?

No. Theorem 1 holds for any maps, but which side of Corollary 2 a protocol falls on depends on its own accounting. The toy models in §5 share a graph and a set of quantities and differ in one coefficient; one satisfies route agreement and the others do not.

It is, however, elementary. When every T_e is invertible this is the statement that the sections of a local system are the vectors fixed by its monodromy. The cellular-sheaf form adds two things: it covers maps that lose information, where "do the diagrams commute?" is no longer a question about invertible matrices, and it gives one exact computation for every model.

## 5. Worked example: a toy escrow (`models/toy_fee_routes.yaml`)

Two routes lead from DELIVERED to SETTLED, one direct and one through DISPUTED with the provider upheld. The protocol promises a 1% fee on either route. There is one free parameter, the escrowed amount.

    both routes collect 1/100 of the amount:      dim H⁰ = 1   ROUTES AGREE
    the dispute route collects any other share:   dim H⁰ = 0   ROUTES DISAGREE
        at SETTLED, route deliver > settle versus route deliver > dispute > uphold_provider
        fee: second route minus first = (c − 1/100)·amount

`tests/test_route_agreement.py` runs five disagreeing shares and the agreeing one. The H¹ linter's sheaf gives the same answer for all six, because its maps do not see the fee.

A case study on a real contract is with the maintainer for review and is not part of this branch.

## 6. Limits

- **Linear maps only.** A fee with a minimum or a cap is piecewise affine. An affine map can be handled by adding a constant coordinate; a piecewise one needs a model per region. Neither is implemented.
- **The model is written by hand from the code.** The tool checks the model, not the contract. A model should be tied to its contract by at least one measured execution.
- **The modelling rule is a judgment.** Deciding which quantities are promised to be route-independent is the modeller's claim about the protocol's intent.
- **Authorisation is out of scope.** Two escrows that differ only in who may release funds have the same accounting and are not distinguished.
- **Findings are stated relative to the tree route.** Proposition 3 gives the right subspace A, but a loop that is harmless after the tree route and harmful after another route is reported through the first disagreement, not on its own.
- **One protocol.** An evaluation across independent contracts, with seeded and historical defects and a comparison against an invariant checker, has not been done.

## 7. Relation to prior work (to be completed)

Global sections as the object of interest: Abramsky and Brandenburger (contextuality as the absence of a global section); Felber, Hummes Flores and Rincon Galeana (terminating solutions of a distributed task as global sections of a task sheaf); Ghrist and Hiraoka (H⁰ as the information flows of a network code). Cellular sheaves and their computation: Curry; Hansen and Ghrist; Robinson. State-machine verification of contracts, which checks authorisation and reachability and is complementary: VeriSol, FSolidM and VeriSolid, Obsidian. These citations come from a literature search on 14 November 2026 and have not all been read in full by the authors.
