#include "../AtomS3R_AfskRx/Bell103Overture.h"

#include <assert.h>
#include <math.h>
#include <vector>

static double tonePower(const std::vector<double>& samples,double hz) {
  double real=0,imag=0;
  for(size_t i=0;i<samples.size();++i){
    double angle=6.283185307179586*hz*i/Bell103Overture::SAMPLE_RATE;
    real+=samples[i]*cos(angle);imag+=samples[i]*sin(angle);
  }
  return (real*real+imag*imag)/(samples.size()*samples.size());
}

int main() {
  static_assert(Bell103Overture::SYMBOL_SAMPLES==160,"300 baud at 48 kHz");
  static_assert(Bell103Overture::TOTAL_SAMPLES==537200,"overture duration");
  Bell103Overture overture;
  std::vector<double> dial;
  int32_t stereo[257*2];
  uint32_t position=0;
  while(!overture.finished()){
    size_t count=overture.render(stereo,257);
    assert(count>0&&count<=257);
    for(size_t i=0;i<count;++i,++position){
      assert(stereo[2*i]==stereo[2*i+1]);
      double sample=(double)stereo[2*i]/2147483647.0;
      assert(fabs(sample)<.85);
      if(position>=2400&&position<2400+48000)dial.push_back(sample);
    }
  }
  assert(position==Bell103Overture::TOTAL_SAMPLES);
  assert(overture.render(stereo,257)==0);
  assert(dial.size()==48000);
  assert(tonePower(dial,350)>0.02);
  assert(tonePower(dial,450)>0.02);
  assert(tonePower(dial,1000)<0.001);
  overture.reset();
  assert(overture.position()==0);
}
