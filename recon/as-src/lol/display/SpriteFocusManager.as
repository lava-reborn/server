class lol.display.SpriteFocusManager
{
   var contextMenuPlayer;
   var contextMenuTimer;
   var dispatchEvent;
   var flared;
   var overArr;
   var sf_arr;
   var spt;
   var spt_int;
   var type;
   var activated = false;
   function SpriteFocusManager(t)
   {
      this.type = t;
      lol.events.LEventDispatcher.initialize(this);
      this.sf_arr = new Array();
      this.overArr = new Array();
      this.startPC();
   }
   function addFocus(t, ft, rt)
   {
      var _loc3_;
      if(t instanceof lol.display.SpriteFocus)
      {
         this.__addFocus(t);
      }
      else
      {
         _loc3_ = new lol.display.SpriteFocus(t,ft,rt);
         this.__addFocus(_loc3_);
      }
   }
   function __addFocus(f)
   {
      var _loc3_ = f.target;
      var _loc4_ = this.getFocus(_loc3_);
      if(!_loc4_)
      {
         f.addEventListener(lol.display.SpriteFocus.onSpriteOver,this);
         f.addEventListener(lol.display.SpriteFocus.onSpriteClick,this);
         f.addEventListener(lol.display.SpriteFocus.onSpriteClickUp,this);
         this.sf_arr.push(f);
         f.activate(this.activated);
      }
   }
   function removeFocus(targ)
   {
      var _loc2_ = this.getFocus(targ);
      _loc2_.activate(false);
      _loc2_.removeEventListener(lol.display.SpriteFocus.onSpriteOver,this);
      _loc2_.removeEventListener(lol.display.SpriteFocus.onSpriteClick,this);
      _loc2_.removeEventListener(lol.display.SpriteFocus.onSpriteClickUp,this);
      if(_loc2_ == this.flared)
      {
         this.flared = null;
         this.dispatchEvent({type:lol.display.SpriteFocus.onSpriteOver});
      }
      var _loc3_ = 0;
      while(_loc3_ < this.overArr.length)
      {
         if(this.overArr[_loc3_] == _loc2_)
         {
            this.overArr.splice(_loc3_,1);
            break;
         }
         _loc3_ = _loc3_ + 1;
      }
      _loc3_ = this.getIndex(targ);
      this.sf_arr.splice(_loc3_,1);
      _loc2_.kill();
   }
   function getFocus(targ)
   {
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < this.sf_arr.length)
      {
         _loc3_ = this.sf_arr[_loc2_];
         if(_loc3_.target == targ)
         {
            return this.sf_arr[_loc2_];
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function getIndex(targ)
   {
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < this.sf_arr.length)
      {
         _loc3_ = this.sf_arr[_loc2_];
         if(_loc3_.target == targ)
         {
            return _loc2_;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function spriteOver(obj)
   {
      var _loc4_;
      var _loc2_;
      if(obj.over)
      {
         _loc4_ = false;
         _loc2_ = 0;
         while(_loc2_ < this.overArr.length)
         {
            if(obj.target == this.overArr[_loc2_])
            {
               _loc4_ = true;
               break;
            }
            _loc2_ = _loc2_ + 1;
         }
         if(!_loc4_)
         {
            this.overArr.push(obj.target);
         }
      }
      else
      {
         _loc2_ = 0;
         while(_loc2_ < this.overArr.length)
         {
            if(obj.target == this.overArr[_loc2_])
            {
               this.overArr[_loc2_].flare(false);
               this.overArr.splice(_loc2_,1);
               break;
            }
            _loc2_ = _loc2_ + 1;
         }
      }
      this.checkOvered();
   }
   function checkOvered()
   {
      var _loc4_;
      var _loc2_;
      var _loc3_;
      if(this.overArr.length > 0)
      {
         _loc4_ = -1;
         _loc2_ = 0;
         while(_loc2_ < this.overArr.length)
         {
            _loc3_ = this.overArr[_loc2_].target.getDepth();
            this.overArr[_loc2_].flare(false);
            if(_loc3_ > _loc4_)
            {
               this.flared = this.overArr[_loc2_];
               _loc4_ = _loc3_;
            }
            _loc2_ = _loc2_ + 1;
         }
         this.flared.flare(true);
      }
      else
      {
         this.flared = null;
      }
      this.dispatchEvent({type:lol.display.SpriteFocus.onSpriteOver,flared:this.flared});
      return this.flared;
   }
   function spriteClick(obj)
   {
      if(obj.target == this.flared)
      {
         this.contextMenuPlayer = lol.core.player.Player(this.flared.target.driver);
         if(this.contextMenuPlayer instanceof lol.core.player.Player && this.contextMenuPlayer.id != lol.core.player.Gamer.ID)
         {
            if(Key.isDown(16))
            {
               this.createContextMenu();
            }
            else
            {
               this.contextMenuTimer = new lol.utils.Timeout(this,this.createContextMenu,1000);
               lol.core.SceneShifter.linkWindow.onMouseUp = mx.utils.Delegate.create(this,this._mouseUp);
            }
         }
         this.dispatchEvent({type:lol.display.SpriteFocus.onSpriteClick,flared:this.flared});
      }
   }
   function _mouseUp()
   {
      this.contextMenuTimer.Clear();
      delete lol.core.SceneShifter.linkWindow.onMouseUp;
      delete this.contextMenuPlayer;
   }
   function createContextMenu()
   {
      var _loc2_ = new Array();
      _loc2_.push({linkID:"actionBarter_btn",obj:this,function_str:"actionBarter",data:this.contextMenuPlayer.id});
      _loc2_.push({linkID:"actionPrivat_btn",obj:this,function_str:"actionPrivat",data:this.contextMenuPlayer.id});
      _loc2_.push({linkID:"actionInspect_btn",obj:this,function_str:"actionInspect",data:this.contextMenuPlayer.id});
      var _loc3_ = lol.core.Master.getInstance();
      if(_loc3_)
      {
         if(_loc3_.gamer.partyManager.hasParty() == false || _loc3_.gamer.partyManager.isLeader(0))
         {
            _loc2_.push({linkID:"actionInviteParty_btn",obj:this,function_str:"actionInvite",data:this.contextMenuPlayer.id});
         }
      }
      lol.core.SceneShifter.contextMenuManager.openContextMenu(_loc2_,"actionDropList",this.contextMenuPlayer.playerInfo.name);
      lol.core.SceneShifter.contextMenuManager.addEventListener("selectItem",this,this.clickContext);
      this.contextMenuTimer.Clear();
      delete lol.core.SceneShifter.linkWindow.onMouseUp;
      delete this.contextMenuPlayer;
   }
   function clickContext(obj)
   {
      obj.target.removeEventListener("selectItem",this,this.clickContext);
      var _loc6_;
      var _loc3_;
      var _loc5_;
      var _loc4_;
      if(obj.data.function_str == "actionInspect")
      {
         lol.core.SceneShifter.closeWindow("inspect");
         _loc6_ = lol.core.SceneShifter.openNewWindow("inspect");
         _loc6_.content.setPlayer(obj.data.param);
      }
      else if(obj.data.function_str == "actionBarter")
      {
         lol.core.Master.getInstance().gamer.gotoWalker(obj.data.param,"contact");
      }
      else if(obj.data.function_str == "actionPrivat")
      {
         lol.core.SceneShifter.chat.setPrivateToInputStr(obj.data.param);
      }
      else if(obj.data.function_str == "actionInvite")
      {
         lol.core.Master.getInstance().gamer.sendInviteToParty(obj.data.param);
      }
      else if(obj.data.function_str == "actionProfile")
      {
         _loc3_ = "http://lava-online.ru/exe/user/profile";
         _loc5_ = lol.core.Master.getInstance();
         if(_loc5_ != undefined)
         {
            _loc4_ = obj.data.param;
            trace("obj.data.param = " + obj.data.param);
            if(_loc4_ != undefined && _loc4_ != "")
            {
               _loc3_ = _loc3_ + "/name/" + _loc4_ + "/ref/1";
               trace("url_str = " + _loc3_);
               getURL(_loc3_,"_blank");
            }
         }
      }
   }
   function activate(a)
   {
      var _loc2_;
      if(a != this.activated)
      {
         this.activated = a;
         _loc2_ = 0;
         while(_loc2_ < this.sf_arr.length)
         {
            this.sf_arr[_loc2_].activate(a);
            _loc2_ = _loc2_ + 1;
         }
         if(!a)
         {
            this.flared = null;
            this.overArr = new Array();
         }
      }
   }
   function setColor(target, color)
   {
      var _loc2_ = this.getFocus(target);
      _loc2_.color = color;
      if(_loc2_ == this.flared)
      {
         _loc2_.flare(true);
      }
   }
   function kill()
   {
      var _loc3_ = 0;
      while(_loc3_ < this.overArr.length)
      {
         this.overArr[_loc3_].removeEventListener(lol.display.SpriteFocus.onSpriteOver,this);
         this.overArr[_loc3_].removeEventListener(lol.display.SpriteFocus.onSpriteClick,this);
         this.overArr[_loc3_].removeEventListener(lol.display.SpriteFocus.onSpriteClickUp,this);
         this.overArr[_loc3_].kill();
         this.overArr[_loc3_] = null;
         _loc3_ = _loc3_ + 1;
      }
      this.overArr = null;
      _loc3_ = 0;
      var _loc2_;
      while(_loc3_ < this.sf_arr.length)
      {
         _loc2_ = this.sf_arr[_loc3_];
         _loc2_.removeEventListener(lol.display.SpriteFocus.onSpriteOver,this);
         _loc2_.removeEventListener(lol.display.SpriteFocus.onSpriteClick,this);
         _loc2_.removeEventListener(lol.display.SpriteFocus.onSpriteClickUp,this);
         _loc2_.kill();
         this.sf_arr[_loc3_] = null;
         _loc3_ = _loc3_ + 1;
      }
      this.sf_arr = null;
      this.flared.removeEventListener(lol.display.SpriteFocus.onSpriteOver,this);
      this.flared.removeEventListener(lol.display.SpriteFocus.onSpriteClick,this);
      this.flared.removeEventListener(lol.display.SpriteFocus.onSpriteClickUp,this);
      this.flared = null;
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("SFManager_" + this.type + "_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
