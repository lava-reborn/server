class lol.core.location.HexCell
{
   var emptyDepth;
   var gx;
   var gy;
   var minDepth;
   var num;
   var rx;
   var ry;
   var unreachable;
   var zone;
   static var staticID = "Hex";
   static var reservedDepths = 100;
   function HexCell(n, _gx, _gy, _rx, _ry)
   {
      this.num = n;
      this.rx = _rx;
      this.ry = _ry;
      this.gx = _gx;
      this.gy = _gy;
      this.minDepth = lol.core.location.HexCell.reservedDepths * n + 10;
      this.emptyDepth = this.minDepth;
      this.unreachable = false;
      this.zone = false;
   }
   function inCell(obj)
   {
      this.emptyDepth = this.emptyDepth + 1;
      if(this.emptyDepth > this.minDepth + lol.core.location.HexCell.reservedDepths)
      {
         this.emptyDepth = this.minDepth + lol.core.location.HexCell.reservedDepths + 1;
      }
   }
   function outFromCell(t)
   {
      this.emptyDepth = this.emptyDepth - 1;
      if(this.emptyDepth < this.minDepth + 1)
      {
         this.emptyDepth = this.minDepth + 1;
      }
   }
   function getMinDepth(num)
   {
      return this.emptyDepth;
   }
   function getMaxDepth()
   {
      return this.emptyDepth;
   }
   function toString()
   {
      return this.num.toString();
   }
}
