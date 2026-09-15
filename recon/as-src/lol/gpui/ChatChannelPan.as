class lol.gpui.ChatChannelPan extends lol.gpui.GPUIObject
{
   var W;
   var _xmouse;
   var _ymouse;
   var attachMovie;
   var currentChannel;
   var dispatchEvent;
   var dragObject;
   var getNextHighestDepth;
   var mainList;
   var master;
   var moveToX;
   var moveToY;
   var onMouseMove;
   var openStack_btn;
   var stackCont_mc;
   var stackList;
   var this_mc;
   var CHANNEL_WIDTH = 96;
   var CHANNEL_HEIGHT = 19;
   var resizeFlag = true;
   var dragFlag = true;
   function ChatChannelPan()
   {
      super();
      this.mainList = new Array();
      this.stackList = new Array();
      var _loc3_ = lol.core.SceneShifter.linkGame;
      var _loc4_ = _loc3_.getNextHighestDepth();
      this.stackCont_mc = _loc3_.attachMovie("stackCont_mc","stackCont_mc",_loc4_);
      this.stackCont_mc._visible = false;
      this.master = lol.core.Master.getInstance();
   }
   function resizeEnabled()
   {
      this.resizeFlag = true;
   }
   function initChannel(group, withID)
   {
      var _loc2_ = this.getChannel(group,withID).mc;
      this.currentChannel.backButton.toggled = false;
      this.currentChannel = _loc2_;
      this.currentChannel.backButton.toggled = true;
      this.currentChannel.showLight(false);
      this.dispatchShowChannel(group,withID);
      false;
   }
   function dispatchShowChannel(_group, _withID)
   {
      var _loc3_;
      var _loc2_;
      _loc3_ = !_group ? this.currentChannel.group : _group;
      _loc2_ = !_withID ? this.currentChannel.withID : _withID;
      this.dispatchEvent({type:"showChannel",group:_loc3_,withID:_loc2_});
   }
   function newMessage(group, withID)
   {
      var _loc6_ = false;
      var _loc2_ = this.getChannel(group,withID).mc;
      var _loc3_;
      if(_loc2_)
      {
         if(_loc2_ == this.currentChannel)
         {
            this.dispatchShowChannel(group,withID);
         }
         else
         {
            _loc2_.showLight(true);
            this.checkLightInStack();
         }
      }
      else
      {
         _loc3_ = this.createChannel(group,withID);
         _loc3_.light = true;
         this.checkLightInStack();
      }
   }
   function newChannel(group, withID)
   {
      var _loc2_ = this.getChannel(group,withID).mc;
      var _loc7_;
      var _loc3_;
      var _loc4_;
      if(_loc2_)
      {
         if(_loc2_ == this.currentChannel)
         {
            this.dispatchShowChannel(group,withID);
         }
         else if(_loc2_.where == "stack")
         {
            _loc7_ = this.getIndex(_loc2_,this.stackList);
            _loc3_ = this.stackList[_loc7_];
            _loc4_ = this.mainList[this.mainList.length - 1];
            this.removeChannel(_loc4_.group,_loc4_.withID,"main");
            this.removeChannel(_loc3_.group,_loc3_.withID,"stack");
            this.addToStack(_loc4_.group,_loc4_.withID,0,true);
            this.createChannel(_loc3_.group,_loc3_.withID,0,true);
            this.doLater("initChannel",[_loc3_.group,_loc3_.withID]);
         }
         else
         {
            this.doLater("initChannel",[_loc2_.group,_loc2_.withID]);
         }
      }
      else
      {
         this.createChannel(group,withID);
         this.doLater("initChannel",[group,withID]);
      }
   }
   function createChannel(group, withID, pos, insert)
   {
      var _loc3_;
      var _loc11_ = this.getLinkage(group);
      var _loc8_ = this.getMainPosition();
      var _loc9_;
      var _loc5_;
      var _loc2_;
      var _loc6_;
      if(_loc8_ != undefined)
      {
         _loc9_ = this.getNextHighestDepth();
         _loc3_ = this.attachMovie(_loc11_,"channel" + _loc9_,_loc9_);
         _loc3_.name = this.master.getPlayer(withID).playerInfo.name;
         _loc3_.group = group;
         _loc3_.withID = withID;
         _loc3_.where = "main";
         _loc3_.addEventListener("onPress",this,this.onPressChannel);
         _loc3_.addEventListener("onRelease",this,this.stopDrag);
         _loc3_.addEventListener("onReleaseOutside",this,this.stopDrag);
         _loc3_.addEventListener("closeChannel",this,this.closeChannel);
         _loc5_ = new Object();
         _loc5_.group = group;
         _loc5_.withID = withID;
         _loc5_.mc = _loc3_;
         if(pos != undefined)
         {
            if(insert)
            {
               _loc2_ = pos;
               while(_loc2_ < this.mainList.length)
               {
                  this.mainList[_loc2_].mc._x += this.CHANNEL_WIDTH;
                  _loc2_ = _loc2_ + 1;
               }
               this.mainList.splice(pos,0,_loc5_);
            }
            else
            {
               this.removeChannelMc(this.mainList[pos].mc);
               this.mainList[pos] = _loc5_;
            }
            _loc3_._x = pos * this.CHANNEL_WIDTH;
         }
         else
         {
            _loc3_._x = _loc8_;
            this.mainList.push(_loc5_);
         }
      }
      else
      {
         _loc6_ = this.mainList[this.mainList.length - 1];
         this.removeChannel(_loc6_.group,_loc6_.withID,"main");
         this.createChannel(group,withID,0,true);
         this.addToStack(_loc6_.group,_loc6_.withID,0,true);
      }
      this.setSizeStackMc();
      return _loc3_;
   }
   function addToStack(group, withID, pos, insert)
   {
      var _loc8_ = this.getLinkage(group);
      var _loc9_ = this.getStackPosition();
      var _loc6_ = this.stackCont_mc.getNextHighestDepth();
      var _loc3_ = this.stackCont_mc.attachMovie(_loc8_,"channel" + _loc6_,_loc6_);
      _loc3_.name = this.master.getPlayer(withID).playerInfo.name;
      _loc3_.group = group;
      _loc3_.withID = withID;
      _loc3_.addEventListener("onPress",this,this.onPressChannel);
      _loc3_.addEventListener("onRelease",this,this.stopDrag);
      _loc3_.addEventListener("onReleaseOutside",this,this.stopDrag);
      _loc3_.addEventListener("closeChannel",this,this.closeChannel);
      _loc3_.where = "stack";
      var _loc5_ = new Object();
      _loc5_.group = group;
      _loc5_.withID = withID;
      _loc5_.mc = _loc3_;
      var _loc2_;
      if(pos != undefined)
      {
         if(insert)
         {
            _loc2_ = pos;
            while(_loc2_ < this.stackList.length)
            {
               this.stackList[_loc2_].mc._y -= this.CHANNEL_HEIGHT;
               _loc2_ = _loc2_ + 1;
            }
            this.stackList.splice(pos,0,_loc5_);
         }
         else
         {
            this.removeChannelMc(this.stackList[pos].mc);
            this.stackList[pos] = _loc5_;
         }
         _loc3_._y = (- pos) * this.CHANNEL_HEIGHT - this.CHANNEL_HEIGHT;
      }
      else
      {
         _loc3_._y = _loc9_;
         this.stackList.push(_loc5_);
      }
      if(!this.openStack_btn)
      {
         _loc6_ = this.getNextHighestDepth();
         this.openStack_btn = this.attachMovie("hideChannelList","openStack_btn",_loc6_);
         this.openStack_btn._x = this.mainList.length * this.CHANNEL_WIDTH;
         this.openStack_btn.addEventListener("onRelease",this,this.showStack);
      }
      this.setSizeStackMc();
      return _loc3_;
   }
   function removeChannel(group, withID, from)
   {
      var _loc2_;
      if(from == "stack")
      {
         _loc2_ = this.stackList;
      }
      else if(from == "main")
      {
         _loc2_ = this.mainList;
      }
      var _loc4_;
      var _loc3_ = 0;
      while(_loc3_ < _loc2_.length)
      {
         if(_loc2_[_loc3_].group == group && _loc2_[_loc3_].withID == withID)
         {
            _loc4_ = _loc3_;
            break;
         }
         _loc3_ = _loc3_ + 1;
      }
      if(from == "stack")
      {
         _loc3_ = _loc4_ + 1;
         while(_loc3_ < _loc2_.length)
         {
            _loc2_[_loc3_].mc._y += this.CHANNEL_HEIGHT;
            _loc3_ = _loc3_ + 1;
         }
      }
      else if(from == "main")
      {
         _loc3_ = _loc4_ + 1;
         while(_loc3_ < _loc2_.length)
         {
            _loc2_[_loc3_].mc._x -= this.CHANNEL_WIDTH;
            _loc3_ = _loc3_ + 1;
         }
      }
      _loc2_[_loc4_].mc.removeMovieClip();
      _loc2_.splice(_loc4_,1);
   }
   function replaceChannel(mainI, stackI)
   {
      var _loc2_ = this.mainList[mainI];
      this.createChannel(_loc2_.group,_loc2_.withID,mainI,true);
      var _loc3_ = this.stackList[stackI];
      this.stackList[stackI].mc.removeMovieClip();
      this.addToStack(_loc3_.group,_loc3_.withID,stackI,true);
   }
   function showStack(obj)
   {
      this.stackCont_mc._visible = obj.target.backButton.toggled;
      this.checkLightInStack();
   }
   function onPressChannel(obj)
   {
      this.dragObject = new Object();
      this.dragObject.what = obj.target;
      if(obj.target.where == "main")
      {
         if(this.currentChannel != obj.target)
         {
            this.currentChannel.backButton.toggled = false;
            this.currentChannel = obj.target;
         }
         else
         {
            this.currentChannel.backButton.toggled = true;
         }
      }
      else if(obj.target.where == "stack")
      {
         obj.target.backButton.toggled = false;
      }
      this.onMouseMove = this.startDrag;
      this.dispatchShowChannel();
      this.currentChannel.showLight(false);
   }
   function startDrag()
   {
      this.dragObject.dragFlag = true;
      var _loc3_ = new flash.display.BitmapData(this.dragObject.what._width,this.dragObject.what._height,true,0);
      var _loc2_ = lol.core.SceneShifter.linkGame;
      var _loc4_ = _loc2_.getNextHighestDepth();
      this.dragObject.mc = _loc2_.createEmptyMovieClip("dragChannelCont",_loc4_);
      this.dragObject.mc.attachBitmap(_loc3_,this.dragObject.mc.getNextHighestDepth());
      _loc3_.draw(this.dragObject.what);
      this.dragObject.shiftX = this.dragObject.what._xmouse;
      this.dragObject.shiftY = this.dragObject.what._ymouse;
      delete this.onMouseMove;
      this.onMouseMove = this.dragChannel;
      this.dragObject.what._visible = false;
      this.dragChannel();
   }
   function dragChannel()
   {
      var _loc6_ = lol.core.SceneShifter.linkGame;
      this.dragObject.mc._x = _loc6_._xmouse - this.dragObject.shiftX;
      this.dragObject.mc._y = _loc6_._ymouse - this.dragObject.shiftY;
      var _loc4_ = this._xmouse;
      var _loc7_ = this._ymouse;
      var _loc8_ = this.stackCont_mc._xmouse;
      var _loc5_ = this.stackCont_mc._ymouse;
      var _loc2_;
      var _loc3_;
      if(_loc7_ > 0 && _loc7_ < this.CHANNEL_HEIGHT)
      {
         _loc2_ = 0;
         while(_loc2_ < this.mainList.length)
         {
            _loc3_ = this.mainList[_loc2_].mc;
            if(_loc4_ > _loc3_._x && _loc4_ < _loc3_._x + this.CHANNEL_WIDTH && _loc3_ != this.dragObject.what && this.dragFlag)
            {
               this.exchangeWithAnimation("main",_loc2_);
               break;
            }
            _loc2_ = _loc2_ + 1;
         }
         if(_loc4_ > this.mainList.length * this.CHANNEL_WIDTH && _loc4_ < this.mainList.length * this.CHANNEL_WIDTH + this.openStack_btn._width && !this.stackCont_mc._visible)
         {
            this.showStackList(true);
         }
      }
      else if(_loc8_ > 0 && _loc8_ < this.CHANNEL_WIDTH)
      {
         _loc2_ = 0;
         while(_loc2_ < this.stackList.length)
         {
            _loc3_ = this.stackList[_loc2_].mc;
            if(_loc5_ > _loc3_._y && _loc5_ < _loc3_._y + this.CHANNEL_HEIGHT && _loc3_ != this.dragObject.what && this.dragFlag && this.stackCont_mc._visible)
            {
               this.exchangeWithAnimation("stack",_loc2_);
               break;
            }
            _loc2_ = _loc2_ + 1;
         }
      }
   }
   function stopDrag(obj)
   {
      delete this.onMouseMove;
      this.moveDragContTo();
      this.currentChannel.backButton.toggled = true;
      if(this.dragObject.dragFlag && obj.target.where == "stack")
      {
         obj.target.backButton.toggled = false;
      }
      var _loc5_;
      var _loc2_;
      var _loc3_;
      var _loc6_;
      if(!this.dragObject.dragFlag && obj.target.where == "stack")
      {
         this.currentChannel.backButton.toggled = false;
         _loc5_ = this.getIndex(obj.target,this.stackList);
         _loc2_ = this.stackList[_loc5_];
         _loc3_ = this.mainList[this.mainList.length - 1];
         this.removeChannel(_loc3_.group,_loc3_.withID,"main");
         this.removeChannel(_loc2_.group,_loc2_.withID,"stack");
         this.addToStack(_loc3_.group,_loc3_.withID,0,true);
         _loc6_ = this.createChannel(_loc2_.group,_loc2_.withID,0,true);
         this.doLater("initChannel",[_loc2_.group,_loc2_.withID]);
      }
   }
   function exchangeWithAnimation(type, tempI)
   {
      var _loc8_;
      var _loc7_;
      var _loc4_;
      var _loc2_;
      var _loc10_;
      var _loc5_;
      var _loc3_;
      if(this.dragObject.what.where == "main" && type == "main")
      {
         this.showStackList(false);
         _loc8_ = this.dragObject.what;
         _loc7_ = this.mainList[tempI].mc;
         _loc4_ = this.getIndex(this.dragObject.what,this.mainList);
         _loc2_ = tempI;
         if(_loc8_._x < _loc7_._x)
         {
            this.slideGroupOfChannel(this.mainList,_loc4_ + 1,_loc2_,- this.CHANNEL_WIDTH,0);
         }
         else if(_loc8_._x > _loc7_._x)
         {
            this.slideGroupOfChannel(this.mainList,_loc2_,_loc4_ - 1,this.CHANNEL_WIDTH,0);
         }
         this.dragObject.what._x = _loc2_ * this.CHANNEL_WIDTH;
         _loc10_ = this.mainList[_loc4_];
         this.mainList.splice(_loc4_,1);
         this.mainList.splice(_loc2_,0,_loc10_);
      }
      else if(this.dragObject.what.where == "stack" && type == "stack")
      {
         _loc8_ = this.dragObject.what;
         _loc7_ = this.stackList[tempI].mc;
         _loc4_ = this.getIndex(this.dragObject.what,this.stackList);
         _loc2_ = tempI;
         if(_loc8_._y < _loc7_._y)
         {
            this.slideGroupOfChannel(this.stackList,_loc2_,_loc4_ - 1,0,- this.CHANNEL_HEIGHT);
         }
         else if(_loc8_._y > _loc7_._y)
         {
            this.slideGroupOfChannel(this.stackList,_loc4_ + 1,_loc2_,0,this.CHANNEL_HEIGHT);
         }
         this.dragObject.what._y = (- _loc2_) * this.CHANNEL_HEIGHT - this.CHANNEL_HEIGHT;
         _loc10_ = this.stackList[_loc4_];
         this.stackList.splice(_loc4_,1);
         this.stackList.splice(_loc2_,0,_loc10_);
      }
      else if(this.dragObject.what.where == "main" && type == "stack")
      {
         _loc4_ = this.getIndex(this.dragObject.what,this.mainList);
         _loc5_ = this.mainList[_loc4_];
         _loc3_ = this.stackList[0];
         this.slideGroupOfChannel(this.mainList,_loc4_ + 1,this.mainList.length - 1,- this.CHANNEL_WIDTH,0);
         this.mainList.splice(_loc4_,1);
         this.createChannel(_loc3_.group,_loc3_.withID);
         this.addToStack(_loc5_.group,_loc5_.withID,0,false);
         this.doLater("initChannel",[this.mainList[_loc4_].group,this.mainList[_loc4_].withID]);
         this.dragObject.what = this.stackList[0].mc;
         this.dragObject.what._visible = false;
      }
      else if(this.dragObject.what.where == "stack" && type == "main")
      {
         _loc4_ = this.getIndex(this.dragObject.what,this.stackList);
         _loc5_ = this.mainList[this.mainList.length - 1];
         _loc3_ = this.stackList[_loc4_];
         this.slideGroupOfChannel(this.stackList,0,_loc4_,0,- this.CHANNEL_HEIGHT);
         this.stackList.splice(_loc4_,1);
         this.stackList.splice(0,0,_loc5_);
         this.addToStack(_loc5_.group,_loc5_.withID,0,false);
         this.removeChannelMc(this.mainList[this.mainList.length - 1].mc);
         this.mainList.splice(this.mainList.length - 1,1);
         this.createChannel(_loc3_.group,_loc3_.withID);
         this.dragObject.what = this.mainList[this.mainList.length - 1].mc;
         this.dragObject.what._visible = false;
         this.doLater("initChannel",[_loc3_.group,_loc3_.withID]);
      }
   }
   function slideGroupOfChannel(arr, start, end, shiftX, shiftY)
   {
      var _loc2_ = start;
      while(_loc2_ <= end)
      {
         this.moveChannelTo(arr[_loc2_].mc,arr[_loc2_].mc._x + shiftX,arr[_loc2_].mc._y + shiftY);
         _loc2_ = _loc2_ + 1;
      }
   }
   function moveDragContTo()
   {
      this.dragObject.mc.onEnterFrame = mx.utils.Delegate.create(this,this._moveDragContTo);
   }
   function _moveDragContTo()
   {
      var _loc7_ = this.getCoorInLinkGame.x;
      var _loc6_ = this.getCoorInLinkGame.y;
      var _loc5_ = _loc7_;
      var _loc4_ = _loc6_;
      var _loc3_ = _loc5_ - this.dragObject.mc._x;
      var _loc2_ = _loc4_ - this.dragObject.mc._y;
      if(Math.abs(_loc3_) > 2 || Math.abs(_loc2_) > 2)
      {
         this.dragObject.mc._x += Math.round(_loc3_ / 1.5);
         this.dragObject.mc._y += Math.round(_loc2_ / 1.5);
      }
      else
      {
         this.dragObject.mc._x = _loc5_;
         this.dragObject.mc._y = _loc4_;
         this.drop();
      }
   }
   function moveChannelTo(mc, X, Y)
   {
      mc.moveToX = X;
      mc.moveToY = Y;
      mc.this_mc = lol.core.SceneShifter.chat.channelPan.chatChannelPan;
      mc.onEnterFrame = function()
      {
         this.this_mc._moveChannelTo(this,this.moveToX,this.moveToY);
      };
      this.dragFlag = false;
   }
   function _moveChannelTo(moveToMc, moveToX, moveToY)
   {
      var _loc4_ = moveToX - moveToMc._x;
      var _loc3_ = moveToY - moveToMc._y;
      if(Math.abs(_loc4_) > 2 || Math.abs(_loc3_) > 2)
      {
         moveToMc._x += Math.round(_loc4_ / 1.5);
         moveToMc._y += Math.round(_loc3_ / 1.5);
      }
      else
      {
         moveToMc._x = moveToX;
         moveToMc._y = moveToY;
         delete moveToMc.onEnterFrame;
         this.dragFlag = true;
      }
   }
   function closeChannel(obj)
   {
      var _loc2_ = obj.target;
      var _loc4_ = false;
      if(_loc2_ == this.currentChannel)
      {
         _loc4_ = true;
      }
      var _loc3_;
      var _loc5_;
      if(_loc2_.where == "main")
      {
         _loc3_ = this.stackList[0];
         _loc5_ = this.getIndex(_loc2_,this.mainList);
         this.removeChannel(_loc2_.group,_loc2_.withID,"main");
         this.removeChannel(_loc3_.group,_loc3_.withID,"stack");
         if(_loc3_)
         {
            this.createChannel(_loc3_.group,_loc3_.withID);
         }
         if(_loc4_)
         {
            if(this.mainList[_loc5_])
            {
               this.doLater("initChannel",[this.mainList[0].group,this.mainList[0].withID]);
            }
            else
            {
               this.doLater("initChannel",[this.mainList[0].group,this.mainList[0].withID]);
            }
         }
      }
      else if(_loc2_.where == "stack")
      {
         this.removeChannel(_loc2_.group,_loc2_.withID,"stack");
      }
      this.setSizeStackMc();
   }
   function drop()
   {
      delete this.dragObject.mc.onEnterFrame;
      this.dragObject.mc.removeMovieClip();
      this.dragObject.mc = null;
      this.dragObject.what._visible = true;
   }
   function setSize(_w)
   {
      this.W = _w - 50;
   }
   function resizeStage()
   {
      var _loc4_;
      var _loc3_;
      var _loc6_;
      var _loc5_;
      if(this.resizeFlag)
      {
         if(this.getMainPosition() != undefined && this.stackList.length != 0)
         {
            _loc4_ = this.stackList[0].group;
            _loc3_ = this.stackList[0].withID;
            _loc6_ = this.stackList[0].mc.light;
            this.removeChannel(_loc4_,_loc3_,"stack");
            _loc5_ = this.createChannel(_loc4_,_loc3_);
            _loc5_.light = _loc6_;
            for(var _loc2_ in this.stackList)
            {
            }
            if(this.getMainPosition() != undefined)
            {
               this.resizeStage();
            }
         }
         else if(this.mainList.length * this.CHANNEL_WIDTH > this.W)
         {
            _loc4_ = this.mainList[this.mainList.length - 1].group;
            _loc3_ = this.mainList[this.mainList.length - 1].withID;
            _loc6_ = this.mainList[this.mainList.length - 1].mc.light;
            this.removeChannel(_loc4_,_loc3_,"main");
            _loc5_ = this.addToStack(_loc4_,_loc3_,0,true);
            _loc5_.light = _loc6_;
            if(this.mainList.length * this.CHANNEL_WIDTH > this.W)
            {
               this.resizeStage();
            }
         }
      }
      this.openStack_btn._x = this.mainList.length * this.CHANNEL_WIDTH;
      this.stackCont_mc._y = lol.core.SceneShifter._ref.H - 144;
      this.stackCont_mc._x = this.openStack_btn._x - this.CHANNEL_WIDTH + 55;
      this.checkLightInStack();
   }
   function getMainPosition()
   {
      var _loc2_ = 0;
      if(this.mainList.length * this.CHANNEL_WIDTH + this.CHANNEL_WIDTH < this.W)
      {
         _loc2_ = this.mainList.length * this.CHANNEL_WIDTH;
      }
      else
      {
         _loc2_;
      }
      return _loc2_;
   }
   function getStackPosition()
   {
      var _loc2_ = - this.CHANNEL_HEIGHT;
      _loc2_ = (- this.stackList.length) * this.CHANNEL_HEIGHT - this.CHANNEL_HEIGHT;
      return _loc2_;
   }
   function setSizeStackMc()
   {
      var _loc2_;
      if(this.stackList.length == 0)
      {
         this.openStack_btn.removeMovieClip();
         this.openStack_btn = null;
         this.stackCont_mc._visible = false;
      }
      else
      {
         _loc2_ = this.stackList.length * this.CHANNEL_HEIGHT;
         this.stackCont_mc.resize_mc._y = - _loc2_ - 15;
         this.stackCont_mc.mask_mc._height = Math.abs(this.stackCont_mc.resize_mc._y);
      }
   }
   function get getCoorInLinkGame()
   {
      var _loc2_ = new Object();
      var _loc4_ = this.dragObject.what._x;
      var _loc3_ = this.dragObject.what._y;
      var _loc5_ = this.dragObject.what.where;
      if(_loc5_ == "main")
      {
         _loc2_.x = lol.core.SceneShifter.chat._x + lol.core.SceneShifter.chat.channelPan._x + lol.core.SceneShifter.chat.channelPan.chatChannelPan._x + _loc4_;
         _loc2_.y = lol.core.SceneShifter.chat._y + lol.core.SceneShifter.chat.channelPan._y + lol.core.SceneShifter.chat.channelPan.chatChannelPan._y + _loc3_;
      }
      else if(_loc5_ == "stack")
      {
         _loc2_.x = this.stackCont_mc._x + _loc4_;
         _loc2_.y = this.stackCont_mc._y + _loc3_;
      }
      return _loc2_;
   }
   function removeChannelMc(mc)
   {
      mc.addEventListener("onPress",this,this.onPressChannel);
      mc.addEventListener("onRelease",this,this.stopDrag);
      mc.addEventListener("onReleaseOutside",this,this.stopDrag);
      mc.removeMovieClip();
   }
   function showStackList(value)
   {
      this.openStack_btn.backButton.toggled = value;
      this.stackCont_mc._visible = value;
   }
   function getIndex(mc, arr)
   {
      var _loc1_ = 0;
      while(_loc1_ < arr.length)
      {
         if(arr[_loc1_].mc == mc)
         {
            return _loc1_;
         }
         _loc1_ = _loc1_ + 1;
      }
   }
   function getChannel(group, withID)
   {
      var _loc4_;
      for(var _loc5_ in this.mainList)
      {
         if(this.mainList[_loc5_].group == lol.core.Chat.CHAT_LOCATION_CHANNEL && group == undefined | group == lol.core.Chat.CHAT_LOCATION_CHANNEL && withID != undefined)
         {
            return this.mainList[_loc5_];
         }
         if(this.mainList[_loc5_].group == group && this.mainList[_loc5_].withID == withID)
         {
            _loc4_ = this.mainList[_loc5_];
         }
      }
      if(!_loc4_)
      {
         for(_loc5_ in this.stackList)
         {
            if(this.stackList[_loc5_].group == lol.core.Chat.CHAT_LOCATION_CHANNEL && group == undefined | group == lol.core.Chat.CHAT_LOCATION_CHANNEL && withID != undefined)
            {
               return this.stackList[_loc5_];
            }
            if(this.stackList[_loc5_].group == group && this.stackList[_loc5_].withID == withID)
            {
               _loc4_ = this.stackList[_loc5_];
            }
         }
      }
      return _loc4_;
   }
   function checkLightInStack()
   {
      var _loc2_ = false;
      for(var _loc3_ in this.stackList)
      {
         if(this.stackList[_loc3_].mc.light)
         {
            _loc2_ = true;
         }
      }
      this.openStack_btn.showLight(_loc2_);
   }
   function getLinkage(str)
   {
      switch(str)
      {
         case lol.core.Chat.CHAT_LOCATION_CHANNEL:
            return "channel_main_btn";
         case lol.core.Chat.CHAT_PARTY_CHANNEL:
            return "channel_party_btn";
         case lol.core.Chat.CHAT_CLAN_CHANNEL:
            return "channel_clan_btn";
         case lol.core.Chat.CHAT_EVENT_CHANNEL:
            return "channel_events_btn";
         case lol.core.Chat.CHAT_TRADE_CHANNEL:
            return "channel_trade_btn";
         case lol.core.Chat.CHAT_HELP_CHANNEL:
            return "channel_help_btn";
         case lol.core.Chat.CHAT_WORLD_CHANNEL:
            return "channel_world_btn";
         case lol.core.Chat.CHAT_PRIVATE_CHANNEL:
            return "channel_private_btn";
         default:
            return "channel_btn";
      }
   }
}
