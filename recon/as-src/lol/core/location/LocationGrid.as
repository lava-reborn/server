class lol.core.location.LocationGrid
{
   var CellsGrid;
   var CellsNum;
   var gridH;
   var gridW;
   var obstacle_arr;
   var zone_arr;
   static var angles;
   static var cellW = 40;
   static var cellH = 15;
   function LocationGrid(W, H)
   {
      lol.core.location.LocationGrid.angles = new Array();
      lol.core.location.LocationGrid.angles[0] = 2;
      lol.core.location.LocationGrid.angles[1] = 1;
      lol.core.location.LocationGrid.angles[2] = 8;
      lol.core.location.LocationGrid.angles[3] = 7;
      lol.core.location.LocationGrid.angles[4] = 6;
      lol.core.location.LocationGrid.angles[-1] = 3;
      lol.core.location.LocationGrid.angles[-2] = 4;
      lol.core.location.LocationGrid.angles[-3] = 5;
      this.gridW = W;
      this.gridH = H;
      this.createCells();
   }
   function createCells()
   {
      this.CellsNum = new Array();
      this.CellsGrid = new Array();
      var _loc6_ = 0;
      var _loc7_ = 0.8660254037844386;
      var _loc3_ = 0;
      var _loc2_;
      var _loc5_;
      var _loc4_;
      while(_loc3_ < this.gridH)
      {
         this.CellsGrid[_loc3_] = new Array();
         _loc2_ = 0;
         while(_loc2_ < this.gridW)
         {
            _loc5_ = 0.5 * (_loc3_ % 2);
            _loc4_ = new lol.core.location.HexCell(_loc6_,_loc2_,_loc3_,_loc2_ + _loc5_,_loc3_ * _loc7_);
            this.CellsNum.push(_loc4_);
            this.CellsGrid[_loc3_][_loc2_] = _loc4_;
            _loc6_ = _loc6_ + 1;
            _loc2_ = _loc2_ + 1;
         }
         _loc3_ = _loc3_ + 1;
      }
   }
   function getCellFromNumber(num)
   {
      return this.CellsNum[num];
   }
   function getCellFromReal(xm, ym)
   {
      var _loc2_ = lol.core.location.LocDeclaration.realToGrid({x:xm,y:ym});
      var _loc4_ = _loc2_.x;
      var _loc3_ = _loc2_.y;
      return this.CellsGrid[_loc3_][_loc4_];
   }
   function getCellFromGrid(x, y)
   {
      return this.CellsGrid[y][x];
   }
   function getSiblings(c)
   {
      var _loc3_ = new Array();
      var _loc5_ = c.gx;
      var _loc4_ = c.gy;
      var _loc2_;
      _loc2_ = this.getCellFromGrid(_loc5_ - 1,_loc4_);
      if(_loc2_)
      {
         _loc3_.push(_loc2_);
      }
      _loc2_ = this.getCellFromGrid(_loc5_ + 1,_loc4_);
      if(_loc2_)
      {
         _loc3_.push(_loc2_);
      }
      _loc2_ = this.getCellFromGrid(_loc5_,_loc4_ - 1);
      if(_loc2_)
      {
         _loc3_.push(_loc2_);
      }
      _loc2_ = this.getCellFromGrid(_loc5_,_loc4_ + 1);
      if(_loc2_)
      {
         _loc3_.push(_loc2_);
      }
      var _loc6_ = 2 * (_loc4_ % 2) - 1;
      _loc2_ = this.getCellFromGrid(_loc5_ + _loc6_,_loc4_ + 1);
      if(_loc2_)
      {
         _loc3_.push(_loc2_);
      }
      _loc2_ = this.getCellFromGrid(_loc5_ + _loc6_,_loc4_ - 1);
      if(_loc2_)
      {
         _loc3_.push(_loc2_);
      }
      return _loc3_;
   }
   function isSiblings(cell1, cell2)
   {
      var _loc3_ = this.getSiblings(cell1);
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_] == cell2)
         {
            return true;
         }
         _loc2_ = _loc2_ + 1;
      }
      return false;
   }
   function get width()
   {
      return this.gridW;
   }
   function get height()
   {
      return this.gridH;
   }
   function getDirection(pos0, pos1)
   {
      var _loc7_ = lol.core.location.LocationGrid.angles;
      var _loc6_ = this.getCellFromNumber(pos0);
      var _loc5_ = this.getCellFromNumber(pos1);
      var _loc4_ = _loc5_.rx - _loc6_.rx;
      var _loc2_ = _loc5_.ry - _loc6_.ry;
      var _loc3_;
      if(_loc4_ < 0)
      {
         if(_loc2_ > 0)
         {
            _loc3_ = -1;
         }
         else if(_loc2_ == 0)
         {
            _loc3_ = -2;
         }
         else if(_loc2_ < 0)
         {
            _loc3_ = -3;
         }
      }
      else if(_loc4_ > 0)
      {
         if(_loc2_ > 0)
         {
            _loc3_ = 1;
         }
         else if(_loc2_ == 0)
         {
            _loc3_ = 2;
         }
         else if(_loc2_ < 0)
         {
            _loc3_ = 3;
         }
      }
      return _loc7_[_loc3_];
   }
   function getHexDistance(cell0, cell1)
   {
      var _loc2_ = cell0.rx - cell1.rx;
      var _loc1_ = cell0.ry - cell1.ry;
      return Math.sqrt(_loc2_ * _loc2_ + _loc1_ * _loc1_);
   }
   function setObstacles(arr)
   {
      this.obstacle_arr = new Array();
      var _loc2_ = 0;
      var _loc4_;
      var _loc3_;
      while(_loc2_ < arr.length)
      {
         _loc4_ = arr[_loc2_].x;
         _loc3_ = arr[_loc2_].y;
         this.CellsGrid[_loc3_][_loc4_].unreachable = true;
         this.obstacle_arr.push(this.CellsGrid[_loc3_][_loc4_]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function setZones(arr)
   {
      this.zone_arr = new Array();
      var _loc2_ = 0;
      var _loc4_;
      var _loc3_;
      while(_loc2_ < arr.length)
      {
         _loc4_ = arr[_loc2_].x;
         _loc3_ = arr[_loc2_].y;
         this.CellsGrid[_loc3_][_loc4_].zone = true;
         this.zone_arr.push(this.CellsGrid[_loc3_][_loc4_]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function searchWay(x1, y1, x2, y2, zx, zy, ww, hh)
   {
      var _loc5_ = new Array();
      _loc5_[1] = new Array();
      _loc5_[2] = new Array();
      var _loc18_ = Number(ww);
      var _loc20_ = Number(hh);
      var _loc30_ = x1;
      var _loc31_ = y1;
      var _loc28_ = x2;
      var _loc29_ = y2;
      var _loc26_ = [];
      var _loc4_ = [];
      _loc5_[1].push(_loc28_);
      _loc5_[1].push(_loc29_);
      var _loc17_ = 0;
      var _loc12_;
      while(_loc17_ < _loc20_)
      {
         _loc4_[_loc17_] = [];
         _loc12_ = 0;
         while(_loc12_ < _loc18_)
         {
            _loc4_[_loc17_][_loc12_] = 1254;
            _loc12_ = _loc12_ + 1;
         }
         _loc17_ = _loc17_ + 1;
      }
      var _loc27_ = zy + _loc20_;
      var _loc24_ = zx + _loc18_;
      var _loc25_ = lol.core.Master.getInstance().currentLocation.locInfo.battle;
      var _loc38_;
      var _loc16_;
      _loc17_ = zy;
      while(_loc17_ < _loc27_)
      {
         _loc12_ = zx;
         while(_loc12_ < _loc24_)
         {
            _loc16_ = this.CellsGrid[_loc17_][_loc12_];
            if(_loc16_.unreachable || (!_loc16_.alwaysBusy ? (!_loc25_ ? false : _loc16_.busy) : true))
            {
               _loc4_[_loc17_ - zy][_loc12_ - zx] = 1255;
            }
            _loc12_ = _loc12_ + 1;
         }
         _loc17_ = _loc17_ + 1;
      }
      _loc4_[_loc31_][_loc30_] = 1253;
      _loc4_[_loc29_][_loc28_] = 0;
      var _loc7_ = 0;
      var _loc23_ = 1252;
      var _loc3_ = _loc28_;
      var _loc2_ = _loc29_;
      var _loc15_ = 1;
      var _loc6_ = 2;
      var _loc10_;
      while(_loc7_ < _loc23_)
      {
         while(_loc5_[_loc15_].length > 0)
         {
            _loc2_ = _loc5_[_loc15_].pop();
            _loc3_ = _loc5_[_loc15_].pop();
            _loc10_ = -1 + ((_loc2_ + zy) / 2 - Math.floor((_loc2_ + zy) / 2)) * 4;
            if(_loc3_ + 1 < _loc18_ && _loc4_[_loc2_][_loc3_ + 1] == 1254)
            {
               _loc4_[_loc2_][_loc3_ + 1] = _loc7_ + 1;
               _loc5_[_loc6_].push(_loc3_ + 1);
               _loc5_[_loc6_].push(_loc2_);
            }
            if(_loc3_ - 1 >= 0 && _loc4_[_loc2_][_loc3_ - 1] == 1254)
            {
               _loc4_[_loc2_][_loc3_ - 1] = _loc7_ + 1;
               _loc5_[_loc6_].push(_loc3_ - 1);
               _loc5_[_loc6_].push(_loc2_);
            }
            if(_loc2_ + 1 < _loc20_)
            {
               if(_loc4_[_loc2_ + 1][_loc3_] == 1254)
               {
                  _loc4_[_loc2_ + 1][_loc3_] = _loc7_ + 1;
                  _loc5_[_loc6_].push(_loc3_);
                  _loc5_[_loc6_].push(_loc2_ + 1);
               }
               if(_loc4_[_loc2_ + 1][_loc3_ + _loc10_] == 1254)
               {
                  _loc4_[_loc2_ + 1][_loc3_ + _loc10_] = _loc7_ + 1;
                  _loc5_[_loc6_].push(_loc3_ + _loc10_);
                  _loc5_[_loc6_].push(_loc2_ + 1);
               }
            }
            if(_loc2_ > 0)
            {
               if(_loc4_[_loc2_ - 1][_loc3_] == 1254)
               {
                  _loc4_[_loc2_ - 1][_loc3_] = _loc7_ + 1;
                  _loc5_[_loc6_].push(_loc3_);
                  _loc5_[_loc6_].push(_loc2_ - 1);
               }
               if(_loc4_[_loc2_ - 1][_loc3_ + _loc10_] == 1254)
               {
                  _loc4_[_loc2_ - 1][_loc3_ + _loc10_] = _loc7_ + 1;
                  _loc5_[_loc6_].push(_loc3_ + _loc10_);
                  _loc5_[_loc6_].push(_loc2_ - 1);
               }
            }
         }
         _loc15_ = 3 - _loc15_;
         _loc6_ = 3 - _loc15_;
         _loc7_ = _loc7_ + 1;
      }
      _loc3_ = _loc30_;
      _loc2_ = _loc31_;
      _loc7_ = 0;
      _loc23_ = 1252;
      var _loc8_ = 1253;
      var _loc32_ = 0;
      var _loc14_;
      var _loc11_;
      var _loc9_;
      var _loc21_;
      var _loc22_;
      while(_loc8_ > 0 and _loc7_ < _loc23_)
      {
         _loc14_ = _loc3_ - 1 + ((_loc2_ + zy) / 2 - Math.floor((_loc2_ + zy) / 2)) * 4;
         _loc11_ = Number(_loc3_);
         _loc9_ = Number(_loc2_);
         _loc3_ = Number(_loc3_);
         _loc2_ = Number(_loc2_);
         _loc21_ = _loc8_;
         if(_loc2_ + 1 < _loc20_)
         {
            if(_loc4_[_loc2_ + 1][_loc3_] < _loc8_)
            {
               _loc9_ = _loc2_ + 1;
               _loc11_ = _loc3_;
               _loc8_ = _loc4_[_loc9_][_loc11_];
            }
            if(_loc14_ < _loc18_ and _loc14_ >= 0 and _loc4_[_loc2_ + 1][_loc14_] < _loc8_)
            {
               _loc9_ = _loc2_ + 1;
               _loc11_ = _loc14_;
               _loc8_ = _loc4_[_loc9_][_loc11_];
            }
         }
         if(_loc2_ > 0)
         {
            if(_loc4_[_loc2_ - 1][_loc3_] < _loc8_)
            {
               _loc9_ = _loc2_ - 1;
               _loc11_ = _loc3_;
               _loc8_ = _loc4_[_loc9_][_loc11_];
            }
            if(_loc14_ < _loc18_ and _loc14_ >= 0 and _loc4_[_loc2_ - 1][_loc14_] < _loc8_)
            {
               _loc9_ = _loc2_ - 1;
               _loc11_ = _loc14_;
               _loc8_ = _loc4_[_loc9_][_loc11_];
            }
         }
         if(_loc3_ > 0 and _loc4_[_loc2_][_loc3_ - 1] < _loc8_)
         {
            _loc11_ = _loc3_ - 1;
            _loc9_ = _loc2_;
            _loc8_ = _loc4_[_loc9_][_loc11_];
         }
         if(_loc3_ + 1 < _loc18_ and _loc4_[_loc2_][_loc3_ + 1] < _loc8_)
         {
            _loc11_ = _loc3_ + 1;
            _loc9_ = _loc2_;
            _loc8_ = _loc4_[_loc9_][_loc11_];
         }
         if(_loc21_ == _loc8_)
         {
            _loc8_ = -1;
         }
         else
         {
            _loc22_ = [Number(_loc11_ + zx),Number(_loc9_ + zy)];
            _loc26_.push(_loc22_);
            _loc3_ = Number(_loc11_);
            _loc2_ = Number(_loc9_);
         }
         _loc7_ = _loc7_ + 1;
      }
      false;
      return _loc26_;
   }
   function isUnreachible(cell)
   {
      var _loc2_;
      var _loc4_ = lol.core.Master.getInstance().currentLocation.locInfo.battle;
      var _loc1_ = !_loc4_ ? false : cell.busy;
      _loc1_ = !cell.alwaysBusy ? _loc1_ : true;
      if(cell.unreachable || _loc1_)
      {
         _loc2_ = true;
      }
      else
      {
         _loc2_ = false;
      }
      return _loc2_;
   }
}
