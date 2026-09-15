class lol.gpui.view.SlideWindowContainer extends lol.gpui.GPUIObject
{
   var _alpha;
   var _x;
   var activeWindow;
   var closeNum;
   var close_btn;
   var dispatchEvent;
   var linkID;
   var linkIDList;
   var main;
   var modeLink;
   var onEnterFrame;
   var windowList;
   var shift = 12;
   var deleteFlag = false;
   var isWindow = false;
   var span = 12;
   function SlideWindowContainer()
   {
      super();
   }
   function newGroupWindow(winObj, link, m, prop)
   {
      this.modeLink = winObj.modeLink;
      this.main = m;
      this.deleteFlag = false;
      this.linkID = winObj.linkID;
      var _loc8_ = winObj.mode;
      this.windowList = new Array();
      this.linkIDList = new Array();
      if(prop)
      {
         this.span = prop.span;
      }
      var _loc3_ = this.linkID.length - 1;
      var _loc6_;
      var _loc2_;
      var _loc4_;
      while(_loc3_ >= 0)
      {
         _loc6_ = this.main.winContainer.getNextHighestDepth();
         _loc2_ = this.main.winContainer.attachMovie("slideWindow","slideWindow" + _loc6_,_loc6_);
         winObj.instance = _loc2_;
         _loc2_.isDrag = winObj.drag;
         _loc2_.linkID = this.linkID[_loc3_];
         _loc2_.fillContent(this.linkID[_loc3_]);
         _loc2_.bottom = _loc3_ * this.span;
         _loc2_.top = (_loc3_ + 1) * this.span - _loc2_.content.bg._height;
         _loc2_.topClose = _loc2_.top - 50 - this.span;
         _loc2_._y = _loc2_.topClose;
         _loc2_.content.addEventListener("slideWin",this);
         _loc2_.content.addEventListener("openWin",this);
         _loc4_ = (- _loc2_.content.bg._width) / 2;
         _loc2_._x = _loc4_;
         this.windowList.push(_loc2_);
         this.activeWindow = this.linkID[_loc3_];
         _loc3_ = _loc3_ - 1;
      }
      if(winObj.closeBtn)
      {
         _loc6_ = this.main.winContainer.getNextHighestDepth();
         this.close_btn = this.main.winContainer.attachMovie("equip_close_btn","equip_close_btn",_loc6_);
         this.close_btn._x = -100;
         this.close_btn._y = 15;
         this.close_btn._alpha = 0;
         this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.closeWinBtn_func);
         this.close_btn.hint = "closeEquip_btn";
         this.animationCloseBtn("in");
      }
   }
   function kill()
   {
      for(var _loc2_ in this.windowList)
      {
         this.windowList[_loc2_].content.kill();
      }
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.closeWinBtn_func);
   }
   function closeWinBtn_func()
   {
      this.dispatchEvent({type:"close"});
      this.animationCloseBtn("out");
   }
   function animationCloseBtn(str)
   {
      if(str == "in")
      {
         delete this.onEnterFrame;
         var path;
         var param = 388;
         this.close_btn.onEnterFrame = function()
         {
            path = param - this._x;
            this._x += path / 4;
            this._alpha += 5;
            if(Math.abs(path) < 1)
            {
               this._alpha = 100;
               delete this.onEnterFrame;
            }
         };
      }
      else if(str == "out")
      {
         delete this.onEnterFrame;
         var path;
         var param = -100;
         this.close_btn.onEnterFrame = function()
         {
            path = param - this._x;
            this._x += path / 4;
            this._alpha -= 5;
            if(Math.abs(path) < 1)
            {
               this._alpha = 0;
               delete this.onEnterFrame;
            }
         };
      }
   }
   function closeWin()
   {
      this.closeNum = 0;
      var _loc2_ = this.windowList.length - 1;
      while(_loc2_ >= 0)
      {
         this.windowList[_loc2_].deleteFlag = true;
         this.windowList[_loc2_].rollClose();
         this.windowList[_loc2_].addEventListener("closeSlideWin",this);
         _loc2_ = _loc2_ - 1;
      }
   }
   function closeSlideWin(obj)
   {
      obj.target.removeEventListener("closeSlideWin",this);
      this.closeNum = this.closeNum + 1;
      if(this.closeNum == this.windowList.length)
      {
         lol.core.SceneShifter._sl.isWindow = false;
         this.dispatchEvent({type:"closeSlideGroup"});
      }
   }
   function openWin(str)
   {
      this.slideWin(str);
   }
   function getWindow(str)
   {
      for(var _loc3_ in this.windowList)
      {
         if(this.windowList[_loc3_].linkID == str)
         {
            return this.windowList[_loc3_];
         }
      }
   }
   function slideWin(str)
   {
      var _loc3_ = false;
      var _loc2_ = this.windowList.length - 1;
      while(_loc2_ >= 0)
      {
         if(this.windowList[_loc2_].linkID == str)
         {
            _loc3_ = true;
            if(!this.windowList[_loc2_].inBottom)
            {
               this.windowList[_loc2_].rollBottom();
            }
         }
         else
         {
            if(!_loc3_)
            {
               if(this.windowList[_loc2_].inBottom)
               {
                  this.windowList[_loc2_].rollTop();
               }
               else if(this.windowList[_loc2_].isClose)
               {
                  this.windowList[_loc2_].rollTop();
               }
            }
            if(!this.windowList[_loc2_].inBottom && _loc3_)
            {
               this.windowList[_loc2_].rollBottom();
            }
         }
         _loc2_ = _loc2_ - 1;
      }
   }
   function getWindowList()
   {
      return this.windowList;
   }
}
