grammar Aellith;

// --- Top level ---
file : clause ('.' clause)* '.'? EOF ;

clause
  : scope? phase? primitive entity entity entity intensity? evidential? parity?   # triad
  | scope? phase? primitive entity entity intensity? evidential? parity?          # dyad
  | scope? phase? primitive entity intensity? evidential? parity?                 # monad
  ;

entity : WORD ROLE ;

primitive : 'en' | 'in' | 'po' | 'th' | 'co' | 'ce' | 'ca' | 'ri' | 'sa' | 'tr' | 're' ;
intensity : 'ka' | 'ke' | 'ku' ;
evidential : 'he' | 'na' ;

ROLE : '-' [abc] ;
WORD : [a-z][a-z]+ ;
WS : [ \t\n\r]+ -> skip ;
