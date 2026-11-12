#include <cassert>
#include <limits>
#include "../renderer/scene_viewport.h"
int main(){
 using hyrulecraft::sceneViewport;
 auto a=sceneViewport(1920,1080,16.f/9);assert(a.x==0&&a.y==0&&a.width==1920&&a.height==1080);
 auto b=sceneViewport(2560,1397,16.f/9);assert(b.width==2484&&b.x==38&&b.y==0&&b.height==1397);
 auto c=sceneViewport(1294,1447,16.f/9);assert(c.width==1294&&c.height==728&&c.y==359);
 auto d=sceneViewport(2560,1440,std::numeric_limits<float>::quiet_NaN());assert(d.width==2560&&d.height==1440);
 auto e=sceneViewport(0,1440,16.f/9);assert(!e.width&&!e.height);
}
