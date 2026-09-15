class lol.services.SelectionRect
{
   var X0;
   var Y0;
   var cont_mc;
   var playersArr;
   var rect_mc;
   var target;
   var rectFlag = false;
   var downed = false;
   function SelectionRect(targ)
   {
      this.target = targ;
      this.cont_mc = this.target.helpers_mc;
   }
   function _onMouseDown()
   {
      this.X0 = this.cont_mc._xmouse;
      this.Y0 = this.cont_mc._ymouse;
      this.downed = true;
      var _loc2_ = new lol.utils.Timeout(this,this.initiateMouseMove,200);
   }
   function initiateMouseMove()
   {
      if(this.downed)
      {
         this.cont_mc.onMouseMove = mx.utils.Delegate.create(this,this._onMouseMove);
         this._onMouseMove();
      }
   }
   function _onMouseUp()
   {
      this.downed = false;
      delete this.cont_mc.onMouseMove;
      this.selectPlayer();
      this.rect_mc.removeMovieClip();
      this.rect_mc = null;
      this.rectFlag = false;
   }
   function _onMouseMove()
   {
      this.rectFlag = true;
      var _loc3_ = this.cont_mc._xmouse;
      var _loc2_ = this.cont_mc._ymouse;
      this.rect_mc.removeMovieClip();
      this.rect_mc = null;
      var _loc6_ = this.cont_mc.getNextHighestDepth();
      this.rect_mc = this.cont_mc.createEmptyMovieClip("rect_mc",_loc6_);
      this.rect_mc._x = 0;
      this.rect_mc._y = 0;
      var _loc5_ = _loc3_ <= this.X0 ? _loc3_ : this.X0;
      var _loc4_ = _loc2_ <= this.Y0 ? _loc2_ : this.Y0;
      var _loc8_ = _loc3_ <= this.X0 ? this.X0 : _loc3_;
      var _loc7_ = _loc2_ <= this.Y0 ? this.Y0 : _loc2_;
      lol.utils.Draw.drawFillRect(this.rect_mc,_loc5_,_loc4_,_loc8_ - _loc5_,_loc7_ - _loc4_,1,16777215,30,0,10);
   }
   function selectPlayer()
   {
      var _loc4_ = this.target.playerList;
      this.playersArr = new Array();
      var _loc2_;
      var _loc3_;
      for(var _loc5_ in _loc4_)
      {
         _loc2_ = false;
         if(this.rect_mc.hitTest(_loc4_[_loc5_]) && _loc5_ != lol.core.player.Gamer.ID)
         {
            _loc3_ = lol.core.Master.getInstance();
            if(_loc3_)
            {
               _loc2_ = _loc3_.playerRegister.gamer.partyManager.inParty(_loc5_);
            }
            else
            {
               _loc2_ = false;
            }
            if(!_loc2_)
            {
               this.playersArr.push(_loc4_[_loc5_]);
            }
         }
      }
      if(this.playersArr.length != 0)
      {
         this.target.cursorManager.selectPlayers(this.playersArr);
      }
   }
}
