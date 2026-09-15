class lol.gpui.ExchangePan extends lol.gpui.GPUIObject
{
   var alert_txt;
   var apply_btn;
   var cancel_btn;
   var cost_num;
   var dir;
   var dispatchEvent;
   var hBar;
   var label_txt;
   var left_txt;
   var maxValue;
   var money_mc;
   var onEnterFrame;
   var right_txt;
   var rightNum = 0;
   var leftNum = 0;
   var mainSize = "rightNum";
   var cost_mod = 1;
   var showCostInGold = false;
   var showCostInBGGold = false;
   var sell_bool = false;
   var sell_num = 1;
   var pause = 10;
   var count = 0;
   function ExchangePan()
   {
      super();
      this.doLater("init");
      this.left_txt.onChanged = mx.utils.Delegate.create(this,this.changedLeft);
      this.right_txt.onChanged = mx.utils.Delegate.create(this,this.changedRight);
      this.left_txt.restrict = "0-9";
      this.right_txt.restrict = "0-9";
      this.alert_txt._visible = false;
   }
   function init()
   {
      this.money_mc._visible = this.cost_num != undefined;
      if(this.showCostInGold)
      {
         this.money_mc.gotoAndStop(2);
      }
      if(this.sell_bool)
      {
         this.rightNum = this.maxValue;
         this.right_txt.text = this.maxValue;
      }
      else
      {
         this.rightNum = 1;
         this.right_txt.text = 1;
      }
      this.printTxt();
      this.hBar.setPosition(0);
      this.hBar.addEventListener("position",this);
      this.hBar.upButton.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.scrUp);
      this.hBar.downButton.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.scrDown);
      this.hBar.upButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrUp_up);
      this.hBar.downButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrDown_up);
      this.hBar.upButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.scrUp_up);
      this.hBar.downButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.scrDown_up);
      this.apply_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sendObj);
      this.cancel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancel);
      this.hBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this.hBar,this.hBar.scrollUp);
      this.hBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this.hBar,this.hBar.stopScroll);
      this.hBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this.hBar,this.hBar.scrollDown);
      this.hBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this.hBar,this.hBar.stopScroll);
      lol.core.SceneShifter.hotKeyManager.addFilter("dialogue");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.cancel);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.APPLY,this,this.sendObj);
      this.hBar.setSize(120);
      this.changedRight();
   }
   function kill()
   {
      this.hBar.removeEventListener("position",this);
      this.hBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.scrUp);
      this.hBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.scrDown);
      this.hBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrUp_up);
      this.hBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrDown_up);
      this.hBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.scrUp_up);
      this.hBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.scrDown_up);
      this.apply_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sendObj);
      this.cancel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancel);
      lol.core.SceneShifter.hotKeyManager.removeFilter("dialogue");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.cancel);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.APPLY,this,this.sendObj);
   }
   function cancel()
   {
      this.dispatchEvent({type:"close"});
   }
   function changedLeft()
   {
      if(this.left_txt.text == "")
      {
         this.left_txt.text = 0;
      }
      if(this.left_txt.text > this.maxValue)
      {
         this.left_txt.text = this.maxValue;
      }
      this.leftNum = this.left_txt.text;
      this.rightNum = this.maxValue - this.leftNum;
      this.right_txt.text = this.rightNum;
      this.countMoney();
      this.hBar.position(this.pos);
   }
   function changedRight()
   {
      if(this.right_txt.text == "")
      {
         this.right_txt.text = 0;
      }
      if(this.right_txt.text > this.maxValue)
      {
         this.right_txt.text = this.maxValue;
      }
      this.rightNum = this.right_txt.text;
      this.leftNum = this.maxValue - this.rightNum;
      this.left_txt.text = this.leftNum;
      this.countMoney();
      this.hBar.position(this.pos);
   }
   function printTxt()
   {
      this.leftNum = this.leftNum <= this.maxValue ? this.leftNum : this.maxValue;
      this.left_txt.text = this.leftNum;
      this.rightNum = this.rightNum <= this.maxValue ? this.rightNum : this.maxValue;
      this.right_txt.text = this.rightNum;
   }
   function position(obj)
   {
      var _loc2_ = obj.pos <= 100 ? obj.pos : 100;
      this.rightNum = Math.round(this.maxValue * _loc2_ / 100);
      this.leftNum = this.maxValue - this.rightNum;
      this.printTxt();
      this.countMoney();
   }
   function sendObj()
   {
      var _loc2_;
      if(Number(this.rightNum) != 0 && this.money_mc.info_txt.text != "0")
      {
         _loc2_ = new Object();
         _loc2_.type = "exchange";
         _loc2_.left = Number(this.leftNum);
         _loc2_.right = Number(this.rightNum);
         this.dispatchEvent(_loc2_);
      }
      else
      {
         this.cancel();
      }
   }
   function countMoney()
   {
      var _loc2_;
      if(this.sell_bool)
      {
         _loc2_ = Math.floor(this.cost_num * this[this.mainSize] * this.cost_mod);
      }
      else
      {
         _loc2_ = Math.ceil(this.cost_num * this[this.mainSize] * this.cost_mod);
      }
      if(!this.showCostInGold)
      {
         this.money_mc.info_txt.text = _loc2_;
      }
      else
      {
         this.money_mc.info_txt.text = Number(_loc2_ / 100);
      }
   }
   function scrollEnterFrame()
   {
      if(this.count >= this.pause)
      {
         if(this.dir != 0)
         {
            this.scrollOnStep();
         }
         else
         {
            delete this.onEnterFrame;
            this.count = 0;
         }
      }
      else if(this.count == 0)
      {
         this.scrollOnStep();
         this.count = this.count + 1;
      }
      else
      {
         this.count = this.count + 1;
      }
   }
   function scrollOnStep()
   {
      if(this.dir > 0)
      {
         if(this.leftNum > 0)
         {
            this.rightNum = this.rightNum + 1;
         }
      }
      else if(this.dir < 0)
      {
         if(this.leftNum < this.maxValue)
         {
            this.rightNum = this.rightNum - 1;
         }
      }
      this.leftNum = this.maxValue - this.rightNum;
      this.hBar.position(this.pos);
      this.printTxt();
      this.countMoney();
   }
   function scrUp(obj)
   {
      this.hBar.removeEventListener("position",this);
      this.dir = -1;
      this.count = 0;
      this.onEnterFrame = mx.utils.Delegate.create(this,this.scrollEnterFrame);
   }
   function scrUp_up()
   {
      this.hBar.addEventListener("position",this);
      this.dir = 0;
   }
   function scrDown(obj)
   {
      this.hBar.removeEventListener("position",this);
      this.dir = 1;
      this.count = 0;
      this.onEnterFrame = mx.utils.Delegate.create(this,this.scrollEnterFrame);
   }
   function scrDown_up()
   {
      this.hBar.addEventListener("position",this);
      this.dir = 0;
   }
   function get pos()
   {
      var _loc2_ = new Object();
      var _loc3_ = this.rightNum / this.maxValue * 100;
      _loc2_.pos = _loc3_;
      return _loc2_;
   }
   function set label(str)
   {
      var _loc2_ = new TextFormat();
      _loc2_.bold = true;
      this.label_txt.text = str;
      this.label_txt.setTextFormat(_loc2_);
   }
   function get label()
   {
      return this.label_txt.text;
   }
}
