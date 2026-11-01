model FalseInv {
  species A @init 1.0
  species B @init 0.0
  reaction f : A -> B @mass_action(k)
  param k in [1.0, 2.0] @assumed
  invariant wrong : A = 1.0
}
