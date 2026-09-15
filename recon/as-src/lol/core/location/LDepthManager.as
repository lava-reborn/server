class lol.core.location.LDepthManager
{
   var gridArr;
   var objectList;
   var redrawSceneFlag;
   var target;
   var turnedArr;
   var reservedDepthsNum = 10;
   var fromDepth = 0;
   function LDepthManager(targ)
   {
      this.target = targ;
      this.target.addEventListener("enterFrame",this);
      this.objectList = this.target.displayList;
      this.createGridArray();
   }
   function getList()
   {
      return this.objectList;
   }
   function removeObject(mc)
   {
      var _loc3_;
      var _loc2_ = 0;
      while(_loc2_ < this.objectList.length)
      {
         _loc3_ = this.objectList[_loc2_];
         if(_loc3_.sprite == mc)
         {
            this.objectList.splice(_loc2_,1);
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      var _loc7_ = this.objectList.point.x;
      var _loc4_ = this.gridArr[_loc7_];
      var _loc6_ = _loc4_.length;
      _loc2_ = 0;
      while(_loc2_ < _loc6_)
      {
         _loc3_ = _loc4_[_loc2_];
         if(_loc3_.sprite == mc)
         {
            _loc4_.splice(_loc2_,1);
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function getIndex(sobj)
   {
      var _loc3_ = sobj.sprite.getDepth() - this.reservedDepthsNum;
      var _loc2_;
      var _loc4_;
      if(this.objectList[_loc3_] != sobj)
      {
         _loc4_ = this.objectList.length;
         _loc2_ = 0;
         while(_loc2_ < _loc4_)
         {
            if(this.objectList[_loc2_] == sobj)
            {
               _loc3_ = _loc2_;
               break;
            }
            _loc2_ = _loc2_ + 1;
         }
      }
      return _loc3_;
   }
   function zSort()
   {
      var _loc4_ = this.objectList.length;
      var _loc3_;
      var _loc2_;
      this.turnedArr = new Array();
      _loc3_ = 0;
      while(_loc3_ < _loc4_)
      {
         _loc2_ = this.objectList[_loc3_];
         if(_loc2_.minD == 1)
         {
            this.findCollisions(_loc2_);
         }
         this.addToGrid(_loc2_);
         _loc3_ = _loc3_ + 1;
      }
      this.turnedArr = null;
      this.objectList.sortOn("minD",Array.NUMERIC);
      this.displayByDepths();
      this.sortGridArray();
   }
   function findCollisions(obj)
   {
      var _loc2_;
      var _loc5_;
      var _loc3_;
      if(!this.turned(obj))
      {
         this.turnedArr.push(obj);
         _loc3_ = 0;
         while(_loc3_ < this.objectList.length)
         {
            _loc2_ = this.objectList[_loc3_];
            if(_loc2_ != obj)
            {
               _loc5_ = this.getCollision(obj,_loc2_);
               if(_loc5_ > 0)
               {
                  if(_loc2_.minD == 1)
                  {
                     this.findCollisions(_loc2_);
                  }
                  obj.minD += _loc2_.minD;
               }
            }
            _loc3_ = _loc3_ + 1;
         }
      }
   }
   function turned(scObj)
   {
      var _loc3_ = false;
      var _loc2_ = 0;
      while(_loc2_ < this.turnedArr.length)
      {
         if(scObj == this.turnedArr[_loc2_])
         {
            _loc3_ = true;
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc3_;
   }
   function getCollision(obj, otherObj)
   {
      var _loc3_ = obj.left;
      var _loc5_ = obj.right;
      var _loc2_ = otherObj.left;
      var _loc4_ = otherObj.right;
      if(_loc3_ == undefined && _loc5_ == undefined)
      {
         return 0;
      }
      if(_loc2_ == undefined && _loc4_ == undefined)
      {
         return 0;
      }
      if(_loc2_.x > _loc5_.x || _loc4_.x < _loc3_.x)
      {
         return 0;
      }
      var _loc11_;
      var _loc8_;
      if(_loc3_.x >= _loc2_.x && _loc3_.x <= _loc4_.x)
      {
         _loc11_ = this.__equal(otherObj.front,_loc3_.x,"x");
         _loc8_ = otherObj.front[_loc11_].y;
         if(_loc3_.y > _loc8_)
         {
            return 1;
         }
         return -1;
      }
      var _loc9_;
      var _loc10_;
      if(_loc2_.x >= _loc3_.x && _loc2_.x <= _loc5_.x)
      {
         _loc9_ = this.__equal(obj.front,_loc2_.x,"x");
         _loc10_ = obj.front[_loc9_].y;
         if(_loc10_ > _loc2_.y)
         {
            return 1;
         }
         return -1;
      }
      return 0;
   }
   function getSimpleCollision(obj, otherObj)
   {
      var _loc2_ = obj.point;
      var _loc3_ = otherObj.left;
      var _loc5_ = otherObj.right;
      if(_loc3_ == undefined && _loc5_ == undefined)
      {
         return 0;
      }
      if(_loc3_.x > _loc2_.x || _loc5_.x < _loc2_.x)
      {
         return 0;
      }
      var _loc7_ = this.__equal(otherObj.front,_loc2_.x,"x");
      var _loc6_ = otherObj.front[_loc7_].y;
      if(_loc2_.y > _loc6_)
      {
         return 1;
      }
      return -1;
   }
   function getSimpleToSimpleCollision(obj, otherObj)
   {
      var _loc2_ = obj.point;
      var _loc1_ = otherObj.point;
      if(_loc1_.x != _loc2_.x)
      {
         return 0;
      }
      if(_loc2_.y > _loc1_.y)
      {
         return 1;
      }
      return -1;
   }
   function __equal(arr, val, param)
   {
      var _loc1_;
      var _loc2_ = arr.length;
      _loc1_ = 0;
      while(_loc1_ < _loc2_)
      {
         if(arr[_loc1_][param] == val)
         {
            return _loc1_;
         }
         _loc1_ = _loc1_ + 1;
      }
   }
   function sortDisplayList(sobj)
   {
      this.listZSort(sobj);
   }
   function listZSort(obj)
   {
      var _loc3_ = this.getIndex(obj);
      var _loc2_;
      var _loc6_ = 0.5 * this.objectList.length;
      if(_loc3_ < _loc6_)
      {
         _loc2_ = this.searchFromTop(obj);
      }
      else
      {
         _loc2_ = this.searchFromBottom(obj);
      }
      var _loc4_;
      if(_loc2_ != _loc3_)
      {
         if(_loc3_ < _loc2_)
         {
            _loc2_ = _loc2_ - 1;
            _loc4_ = _loc3_;
         }
         else
         {
            _loc4_ = _loc2_;
         }
         this.objectList.splice(_loc3_,1);
         this.objectList.splice(_loc2_,0,obj);
         if(_loc4_ < this.fromDepth)
         {
            this.fromDepth = _loc4_;
         }
         this.redrawSceneFlag = true;
      }
   }
   function searchFromTop(obj)
   {
      var _loc7_ = this.objectList.length;
      var _loc2_;
      var _loc6_ = _loc7_;
      var _loc3_;
      _loc2_ = 0;
      var _loc4_;
      while(_loc2_ < _loc7_)
      {
         _loc3_ = this.objectList[_loc2_];
         if(_loc3_ != obj)
         {
            _loc4_ = this.getSimpleCollision(obj,_loc3_);
            if(_loc4_ == -1)
            {
               _loc6_ = _loc2_;
               break;
            }
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc6_;
   }
   function searchFromBottom(obj)
   {
      var _loc7_ = this.objectList.length;
      var _loc2_;
      var _loc6_ = 0;
      var _loc3_;
      _loc2_ = _loc7_;
      var _loc4_;
      while(_loc2_ >= 0)
      {
         _loc3_ = this.objectList[_loc2_];
         if(_loc3_ != obj)
         {
            _loc4_ = this.getSimpleCollision(obj,_loc3_);
            if(_loc4_ == 1)
            {
               _loc6_ = _loc2_ + 1;
               break;
            }
         }
         _loc2_ = _loc2_ - 1;
      }
      return _loc6_;
   }
   function createGridArray()
   {
      this.gridArr = new Array();
      var _loc4_ = this.target.master.currentLocation.locationGrid;
      var _loc3_ = _loc4_.gridW;
      var _loc5_ = _loc4_.gridH;
      var _loc2_ = 0;
      while(_loc2_ < _loc3_)
      {
         this.gridArr[_loc2_] = new Array();
         _loc2_ = _loc2_ + 1;
      }
   }
   function addToGrid(sobj)
   {
      var _loc4_ = sobj.front;
      var _loc5_ = _loc4_.length;
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc5_)
      {
         _loc3_ = _loc4_[_loc2_].x;
         this.gridArr[_loc3_].push(sobj);
         _loc2_ = _loc2_ + 1;
      }
   }
   function sortGridArray()
   {
      var _loc9_ = this.gridArr.length;
      var _loc8_;
      var _loc6_;
      var _loc5_;
      var _loc4_;
      var _loc2_;
      var _loc7_;
      _loc5_ = 0;
      var _loc3_;
      while(_loc5_ < _loc9_)
      {
         _loc8_ = this.gridArr[_loc5_].length;
         _loc7_ = _loc5_;
         _loc4_ = 0;
         while(_loc4_ < _loc8_)
         {
            _loc3_ = this.gridArr[_loc5_][_loc4_];
            _loc6_ = _loc3_.front.length;
            _loc2_ = 0;
            while(_loc2_ < _loc6_)
            {
               if(_loc3_.front[_loc2_].x == _loc7_)
               {
                  _loc3_.currentFrontDepth = _loc3_.front[_loc2_].y;
                  break;
               }
               _loc2_ = _loc2_ + 1;
            }
            _loc4_ = _loc4_ + 1;
         }
         this.gridArr[_loc5_].sortOn("currentFrontDepth",Array.NUMERIC);
         _loc5_ = _loc5_ + 1;
      }
   }
   function moveObject(sobj, cell)
   {
      var _loc3_ = cell.gx;
      var _loc2_ = cell.gy;
      sobj.point = {x:_loc3_,y:_loc2_};
   }
   function rowZSort(sobj)
   {
      var _loc8_ = sobj.point.x;
      var _loc7_ = this.simpleSearch(sobj);
      var _loc3_ = this.gridArr[_loc8_][_loc7_];
      var _loc9_ = !_loc3_.resID ? this.target.master.getPlayer(_loc3_.sprite.id).playerInfo.name : _loc3_.resID;
      this.gridArr[_loc8_].splice(_loc7_ + 1,0,sobj);
      var _loc4_ = this.getIndex(sobj);
      var _loc2_ = this.getIndex(_loc3_) + 1;
      var _loc5_;
      if(_loc2_ != _loc4_)
      {
         if(_loc4_ < _loc2_)
         {
            _loc2_ = _loc2_ - 1;
            _loc5_ = _loc4_;
         }
         else
         {
            _loc5_ = _loc2_;
         }
         if(!_loc3_)
         {
            _loc2_ = 0;
         }
         this.objectList.splice(_loc4_,1);
         this.objectList.splice(_loc2_,0,sobj);
         if(_loc5_ < this.fromDepth)
         {
            this.fromDepth = _loc5_;
         }
         this.redrawSceneFlag = true;
      }
   }
   function simpleSearch(sobj)
   {
      var _loc6_ = sobj.point.x;
      var _loc7_ = sobj.point.y;
      var _loc3_ = this.gridArr[_loc6_];
      var _loc4_ = _loc3_.length;
      var _loc2_;
      var _loc5_;
      _loc2_ = _loc4_ - 1;
      while(_loc2_ >= 0)
      {
         if(_loc3_[_loc2_] != sobj)
         {
            _loc5_ = _loc3_[_loc2_].getFrontHex("x",_loc6_).y;
            if(_loc5_ < _loc7_)
            {
               _loc4_ = _loc2_;
               break;
            }
         }
         _loc2_ = _loc2_ - 1;
      }
      return _loc4_;
   }
   function binarySearch(A, x, k)
   {
      var _loc1_;
      var _loc6_;
      var _loc2_ = 0;
      var _loc4_ = A.length;
      var _loc5_;
      var _loc3_;
      while(true)
      {
         _loc6_ = _loc2_ + (_loc4_ - _loc2_) / 2;
         _loc1_ = Math.floor(_loc6_);
         _loc5_ = A[_loc1_];
         _loc3_ = _loc5_.getFrontHex("x",x).y;
         if(k < _loc3_)
         {
            _loc4_ = _loc1_ - 1;
         }
         else
         {
            if(k <= _loc3_)
            {
               return _loc1_;
            }
            _loc2_ = _loc1_ + 1;
         }
         if(_loc2_ > _loc4_)
         {
            return _loc1_;
         }
      }
   }
   function enterFrame(obj)
   {
      if(this.redrawSceneFlag)
      {
         this.redrawSceneFlag = false;
         this.displayByDepths();
      }
   }
   function displayByDepths()
   {
      var _loc5_ = this.objectList.length;
      var _loc2_;
      var _loc4_;
      var _loc3_;
      _loc2_ = this.fromDepth - 2;
      while(_loc2_ < _loc5_)
      {
         _loc4_ = _loc2_ + this.reservedDepthsNum;
         _loc3_ = this.objectList[_loc2_];
         _loc3_.sprite.swapDepths(_loc4_);
         _loc2_ = _loc2_ + 1;
      }
      this.fromDepth = _loc5_;
   }
   function kill()
   {
      this.target.removeEventListener("enterFrame",this);
   }
}
