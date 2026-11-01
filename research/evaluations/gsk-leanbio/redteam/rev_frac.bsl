model RevFrac {
  species X @init 3.0
  species Y @init 4.3
  reaction forward : X -> Y @mass_action(kf)
  reaction reverse : Y -> X @mass_action(kr)
  param kf in [0.5, 3.0] @assumed
  param kr in [0.7, 2.5] @assumed
  invariant total : X + Y = 7.3
}
