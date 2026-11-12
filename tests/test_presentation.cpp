#include <cassert>
#include "../renderer/presentation_gate.h"
int main() {
 hyrulecraft::PresentationGate g;
 assert(!g.update(1000,false));
 // Brief ready periods during loading must not reveal the overlay.
 for(int i=0;i<6;i++) { assert(!g.update(2000+i*1000,true)); assert(!g.update(2300+i*1000,false)); }
 assert(!g.update(9000,true)); assert(!g.update(9749,true)); assert(g.update(9750,true));
 assert(g.retainDuringPause(11000,10000,10500));
 assert(!g.retainDuringPause(11501,10000,11500));
 assert(!g.retainDuringPause(11000,0,11000));
 assert(!g.retainDuringPause(11000,12000,11000));
 // A terrain frontier after startup must not cause flashing.
 assert(g.update(9800,false)); assert(g.update(10000,true));
 // A loading/disconnected session needs a new stable reveal.
 g.reset(); assert(!g.retainDuringPause(11000,11000,11000)); assert(!g.update(11000,true)); assert(!g.update(11500,false));
 assert(!g.update(12000,true)); assert(g.update(12750,true));
 // Time rollback cannot bypass the stabilization delay.
 g.reset(); assert(!g.update(20000,true)); assert(!g.update(10000,true)); assert(!g.update(10749,true)); assert(g.update(10750,true));
}
