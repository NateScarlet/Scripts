// PositionAlphaKeyerKernel
// VERSION: 0.1
kernel SameKeyer : ImageComputationKernel<ePixelWise> {
  Image<eRead, eAccessPoint> src;
  Image<eWrite, eAccessPoint> dst;

  param:
    float4 color;
    
  local:
  
  void init() {
  };

  void process() {
    dst() = float4(
      fabs(src()[0] - color[0]),
      fabs(src()[1] - color[1]),
      fabs(src()[2] - color[2]),
      fabs(((src()[0] - color[0]) + (src()[1] - color[1]) + (src()[2] - color[2]) )/ 3));
  };
};