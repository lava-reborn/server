class lol.core.location.LocWalker
{
   var angles;
   var cellPos;
   var completedPath;
   var direction;
   var dispatchEvent;
   var finishTime;
   var id;
   var interval;
   var master;
   var moveTime;
   var moveV;
   var numPos;
   var path;
   var prevNumPos;
   var removeEventListener;
   var spt;
   var spt_int;
   var startTime;
   var vx;
   var vy;
   var x;
   var y;
   var damage = 0;
   var sdamage = 0;
   var moveTimer = 40;
   var relation = "neutral";
   function LocWalker(ID, X, Y)
   {
      this.id = ID;
      this.x = Number(X);
      this.y = Number(Y);
      lol.events.LEventDispatcher.initialize(this);
      this.direction = 1;
      this.master = lol.core.Master.getInstance();
      this.defineConstants();
      this.startPC();
   }
   function createMove(_path)
   {
      this.path = _path;
      this.completedPath = new Array();
      this.clearMove();
      this.startMove();
   }
   function finishMove()
   {
      this.clearMove();
      this.dispatchEvent({type:"finishMove"});
   }
   function clearMove()
   {
      clearInterval(this.interval);
   }
   function startMove()
   {
      var _loc9_ = this.path[0];
      var _loc4_ = this.path[1];
      var _loc12_ = this.path.shift();
      this.completedPath.unshift(_loc12_);
      clearInterval(this.interval);
      var _loc8_ = _loc9_.rx;
      var _loc7_ = _loc9_.ry;
      var _loc13_ = _loc4_.rx;
      var _loc10_ = _loc4_.ry;
      var _loc3_ = _loc13_ - _loc8_;
      var _loc2_ = _loc10_ - _loc7_;
      var _loc16_ = Math.round(Math.atan2(_loc3_,_loc2_) * 4 / 3.141592653589793);
      var _loc5_ = this.angles[_loc16_];
      this.direction = _loc5_;
      this.x = _loc8_;
      this.y = _loc7_;
      var _loc14_ = 200;
      var _loc17_ = 1;
      var _loc6_ = _loc17_ / _loc14_;
      this.vx = _loc6_ * this.moveV[_loc5_][0];
      this.vy = _loc6_ * this.moveV[_loc5_][1];
      var _loc11_ = Math.sqrt(this.vx * this.vx + this.vy * this.vy);
      var _loc15_ = Math.sqrt(_loc3_ * _loc3_ + _loc2_ * _loc2_);
      this.startTime = getTimer();
      this.finishTime = _loc15_ / _loc11_;
      this.moveTime = 0;
      this.interval = setInterval(this,"moveToPoint",this.moveTimer,_loc4_);
   }
   function stopMove()
   {
      var _loc2_ = this.master.currentLocation.getCellFromNumber(this.numPos);
      this.master.currentLocation.movePlayer(_loc2_);
   }
   function moveToPoint(cell)
   {
      this.moveDirectionInc();
      if(this.moveTime >= this.finishTime)
      {
         this.finishPathPart(cell);
      }
   }
   function moveDirectionInc()
   {
      var _loc2_ = getTimer();
      var _loc3_ = _loc2_ - this.startTime - this.moveTime;
      this.moveTime = _loc2_ - this.startTime;
      var _loc5_ = this.x + this.vx * _loc3_;
      var _loc4_ = this.y + this.vy * _loc3_;
      this.setPosition(_loc5_,_loc4_);
   }
   function finishPathPart(cell)
   {
      clearInterval(this.interval);
      this.setPosition(cell.rx,cell.ry);
      this.prevNumPos = this.numPos;
      this.numPos = cell.num;
      if(this.path.length > 1)
      {
         this.startMove();
      }
      else
      {
         this.finishMove();
      }
      this.dispatchEvent({type:"finishPart"});
   }
   function setPosition(X, Y)
   {
      this.x = X;
      this.y = Y;
      this.dispatchEvent({type:"position"});
   }
   function breakMove(p)
   {
      this.syncPos(p);
      this.prevNumPos = this.numPos;
      var _loc2_ = this.master.currentLocation.getCellFromNumber(p);
      this.numPos = p;
      var _loc5_ = _loc2_.rx;
      var _loc4_ = _loc2_.ry;
      this.setPosition(_loc5_,_loc4_);
      this.dispatchEvent({type:"finishPart"});
      this.finishMove();
   }
   function getPosition()
   {
      var _loc2_ = new Object();
      _loc2_.x = this.x;
      _loc2_.y = this.y;
      _loc2_.num = this.numPos;
      _loc2_.cell = this.cellPos;
      return _loc2_;
   }
   function syncPos(pos)
   {
      var _loc3_;
      var _loc4_;
      var _loc2_;
      if(this.id == lol.core.player.Gamer.ID && this.master.currentLocation.warStatus)
      {
         _loc3_ = 0;
         _loc2_ = 0;
         while(_loc2_ < this.path.length)
         {
            _loc4_ = this.path[_loc2_];
            _loc3_ = _loc3_ - 1;
            if(_loc4_.num == pos)
            {
               this.master.gamer.apManager.syncAP(_loc3_);
               return undefined;
            }
            _loc2_ = _loc2_ + 1;
         }
         _loc3_ = 0;
         _loc2_ = 0;
         while(_loc2_ < this.completedPath.length)
         {
            _loc4_ = this.completedPath[_loc2_];
            _loc3_ = _loc3_ + 1;
            if(_loc4_.num == pos)
            {
               this.master.gamer.apManager.syncAP(_loc3_);
               return undefined;
            }
            _loc2_ = _loc2_ + 1;
         }
      }
   }
   function kill()
   {
      this.removeEventListener("finishPart",this);
      this.removeEventListener("fire",this);
      if(this.id == lol.core.player.Gamer.ID)
      {
         this.master.gamer.apManager.warState(0);
      }
      this.finishMove();
      if(this.id == lol.core.player.Gamer.ID)
      {
      }
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("LocWalker_" + this.id + "_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
   function damageWalker(dmg, sdmg)
   {
      this.damage += !dmg ? 0 : dmg;
      this.sdamage += !sdmg ? 0 : sdmg;
   }
   function defineConstants()
   {
      var _loc2_ = 1;
      var _loc4_ = 0.5;
      var _loc3_ = 0.8660254037844386;
      this.moveV = new Array();
      this.moveV[1] = [_loc4_,_loc3_ * _loc2_];
      this.moveV[2] = [0,_loc2_];
      this.moveV[3] = [- _loc4_,_loc3_ * _loc2_];
      this.moveV[4] = [-1,0];
      this.moveV[5] = [- _loc4_,(- _loc3_) * _loc2_];
      this.moveV[6] = [0,- _loc2_];
      this.moveV[7] = [_loc4_,(- _loc3_) * _loc2_];
      this.moveV[8] = [1,0];
      this.angles = new Array();
      this.angles[0] = 2;
      this.angles[1] = 1;
      this.angles[2] = 8;
      this.angles[3] = 7;
      this.angles[4] = 6;
      this.angles[-1] = 3;
      this.angles[-2] = 4;
      this.angles[-3] = 5;
   }
}
