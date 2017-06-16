// PositionKeyerKernel
// VERSION: 0.1
kernel PositionKeyer : ImageComputationKernel<ePixelWise> {
  Image<eRead, eAccessPoint, eEdgeClamped> position;
  Image<eWrite, eAccessPoint> dst;

param:
    
  bool invert_x;
  bool invert_y;
  bool enable_x;
  bool enable_y;
  float rotate_y;
  float4 p0_color;
  float4 p1_color;

  void process() {
    const float x = position()[0];
    const float y = position()[1];
    const float z = position()[2];
    
    float rotated_x = cos(rotate_y) * x - sin(rotate_y) * z;
    float rotated_z = cos(rotate_y) * z + sin(rotate_y) * x;
    
    float4 result;
    result[0] = (rotated_x - p0_color[0]) / p1_color[0];
    result[1] = (y - p0_color[1]) / p1_color[1];
    result[2] = (rotated_z - p0_color[2]) / p1_color[2];
    result = clamp(result, float4(0.0f), float4(1.0f));
    
    result[0] = invert_x ? (1 - result[0]) : result[0];
    result[1] = invert_y ? (1 - result[1]) : result[1];
    result[3] = (enable_x ? result[0] : 1) * (enable_y ? result[1] : 1);

    dst() = result;
  }
};