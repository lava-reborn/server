class lol.core.globmap.DisplayMapObject extends MovieClip
{
   var c_mc;
   var dispatchEvent;
   var info_txt;
   var level_mc;
   var onEnterFrame;
   var persID;
   var persName_str;
   var thisDepth;
   var vrad_mc;
   var doubleClickRadius = 5;
   function DisplayMapObject()
   {
      super();
      lol.events.LEventDispatcher.initialize(this);
      lol.utils.EMouse.addEventListener(lol.utils.EMouse.DOUBLE_CLICK,this,this.onDoubleClick);
      this.c_mc.onRollOver = mx.utils.Delegate.create(this,this._onRollOver);
      this.c_mc.onRollOut = mx.utils.Delegate.create(this,this._onRollOut);
      this.c_mc.onReleaseOutside = mx.utils.Delegate.create(this,this._onReleaseOutSide);
      this.c_mc.onRelease = mx.utils.Delegate.create(this,this._onRelease);
      this.c_mc.onPress = mx.utils.Delegate.create(this,this._onPress);
      var _loc3_ = new lol.utils.Timeout(this,this.init,500);
   }
   function init()
   {
      this.persName_str = lol.core.Master.getInstance().getPlayer(this.persID).playerInfo.name;
      this.thisDepth = this.getDepth();
      if(this.persName_str == undefined)
      {
         lol.core.Master.getInstance().getPlayer(this.persID).addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.updateName);
      }
   }
   function updateName(obj)
   {
      this.persName_str = lol.core.Master.getInstance().getPlayer(this.persID).playerInfo.name;
      if(this.persName_str != undefined)
      {
         lol.core.Master.getInstance().getPlayer(this.persID).removeEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.updateName);
      }
   }
   function onDoubleClick()
   {
      var _loc7_ = this._xmouse;
      var _loc5_ = this._xmouse;
      var _loc3_ = - this.doubleClickRadius;
      var _loc2_ = - this.doubleClickRadius;
      var _loc8_ = 2 * this.doubleClickRadius;
      var _loc6_ = 2 * this.doubleClickRadius;
      var _loc4_ = new flash.geom.Rectangle(_loc3_,_loc2_,_loc8_,_loc6_);
      if(!_loc4_.contains(_loc7_,_loc5_))
      {
      }
   }
   function _onRollOver()
   {
      if(this.persName_str != undefined)
      {
         this.showInfo(this.persName_str);
      }
   }
   function _onRollOut()
   {
      if(this.c_mc._currentframe != 3)
      {
         this.showInfo("");
      }
   }
   function ShowName()
   {
      if(this.persName_str != undefined)
      {
         this.showInfo(this.persName_str);
      }
   }
   function HideName()
   {
      this.showInfo("");
   }
   function _onReleaseOutSide()
   {
      if(this.c_mc._currentframe != 3)
      {
         this.showInfo("");
      }
      this.dispatchEvent({type:"playerOnRelease"});
   }
   function _onPress()
   {
      this.dispatchEvent({type:"playerOnPress"});
   }
   function _onRelease()
   {
      this.dispatchEvent({type:"playerOnRelease"});
   }
   function toLocation()
   {
      lol.core.Master.getInstance().changeWorld();
   }
   function position(obj)
   {
      this._x = obj.x;
      this._y = obj.y;
   }
   function attachIcon(linkID)
   {
      this.attachMovie(linkID,"icon",0);
   }
   function showInfo(info)
   {
      this.info_txt.autoSize = true;
      this.info_txt.text = info;
      var _loc2_;
      var _loc10_;
      var _loc5_;
      var _loc8_;
      var _loc9_;
      var _loc4_;
      var _loc3_;
      var _loc7_;
      if(info != "")
      {
         this.info_txt.htmlText = "[" + lol.core.Master.getInstance().getPlayer(this.persID).attributes.level + "] " + this.info_txt.text;
         _loc2_ = 16776960;
         _loc10_ = lol.core.Master.getInstance().getPlayer(this.persID);
         _loc5_ = _loc10_.clanMemberInfo.clanReg;
         _loc8_ = lol.core.Master.getInstance().gamer.clanMemberInfo.clanReg;
         if(_loc5_ == _loc8_)
         {
            _loc2_ = 65280;
         }
         else
         {
            _loc9_ = lol.core.Master.getInstance().gamer.clanMemberInfo.clanInfo;
            _loc4_ = _loc9_.standingArray;
            for(var _loc6_ in _loc4_)
            {
               _loc3_ = _loc4_[_loc6_];
               if(_loc5_ == _loc3_.data)
               {
                  switch(_loc3_.stat)
                  {
                     case 0:
                        _loc2_ = 16776960;
                        break;
                     case 1:
                        _loc2_ = 65280;
                        break;
                     case -1:
                        _loc2_ = 16711680;
                        break;
                     default:
                        _loc2_ = 16776960;
                  }
               }
            }
         }
         _loc7_ = new TextFormat();
         _loc7_.color = _loc2_;
         this.info_txt.setTextFormat(_loc7_);
         this.swapDepths(this._parent.getNextHighestDepth());
      }
      else
      {
         this.level_mc._visible = false;
         this.swapDepths(this.thisDepth);
      }
   }
   function select(value)
   {
      if(value)
      {
         this.c_mc.gotoAndStop(3);
         this.showInfo(this.persName_str);
      }
      else
      {
         if(this.persID != lol.core.Master.getInstance().gamer.id)
         {
            this.c_mc.gotoAndStop(1);
         }
         else
         {
            this.c_mc.gotoAndStop(2);
         }
         this.showInfo("");
      }
   }
   function showVisRad(r)
   {
      var _loc2_ = new lol.utils.Timeout(this,this.__showVisRad,100,r);
   }
   function __showVisRad(r)
   {
      if(this.persID != 0)
      {
         this.vrad_mc._xscale = 0;
         this.vrad_mc._yscale = 0;
         this.vrad_mc._visible = false;
         this.c_mc.gotoAndStop(3);
      }
      else
      {
         this.vrad_mc._xscale = r * 2;
         this.vrad_mc._yscale = r * 2;
      }
   }
   function fade()
   {
      var _loc2_ = new flash.filters.BlurFilter(5,5,1);
      this.filters = new Array(_loc2_);
      this.onEnterFrame = this._fade;
   }
   function _fade()
   {
      this._alpha = this._alpha - 1;
      if(this._alpha <= 10)
      {
         delete this.onEnterFrame;
      }
   }
   function normal()
   {
      this._alpha = 100;
      delete this.onEnterFrame;
      this.filters = new Array();
   }
}
