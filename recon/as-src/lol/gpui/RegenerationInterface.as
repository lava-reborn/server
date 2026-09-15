class lol.gpui.RegenerationInterface extends lol.gpui.GPUIObject
{
   var addMoney_btn;
   var addMoney_txt;
   var cost_txt;
   var freeOfCharge_btn;
   var getURL;
   var paymentAfro_btn;
   var paymentGold_btn;
   var resurrector;
   var timer;
   var timer_txt;
   static var RESURECT_AFRO = 2;
   static var RESURECT_GOLD = 1;
   static var RESURECT_FREE = 0;
   var GOLD_COST = 5;
   var cost_str = "5 голда.";
   var timePause = 15;
   var currentTime = 0;
   function RegenerationInterface()
   {
      super();
      this.doLater("init");
      this.resurrector = lol.core.Master.getInstance().resurrector;
      this.resurrector.addEventListener("resurrect",this);
      lol.core.SceneShifter.closeWindow("exitLoc");
   }
   function init()
   {
      this.freeOfCharge_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.free);
      this.paymentGold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.payGold);
      this.paymentAfro_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.payAfro);
      this.addMoney_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.addMoney);
      lol.core.Master.getInstance().gamer.addEventListener("uiUpd",this,this.uiUpd);
      this.cost_txt.text = this.cost_str;
      var _loc2_ = lol.core.Master.getInstance().gamer.attributes.gold;
      if(_loc2_ < this.GOLD_COST)
      {
         this.paymentGold_btn._visible = false;
      }
      else
      {
         this.addMoney_btn._visible = false;
         this.addMoney_txt._visible = false;
      }
      this.startTimer();
   }
   function kill()
   {
      this.freeOfCharge_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.free);
      this.paymentGold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.payGold);
      this.paymentAfro_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.payAfro);
      this.addMoney_txt.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.addMoney);
      lol.core.Master.getInstance().gamer.removeEventListener("uiUpd",this,this.uiUpd);
   }
   function uiUpd()
   {
      var _loc2_ = lol.core.Master.getInstance().gamer.attributes.gold;
      if(_loc2_ < this.GOLD_COST)
      {
         this.paymentGold_btn._visible = false;
         this.addMoney_btn._visible = true;
         this.addMoney_txt._visible = true;
      }
      else
      {
         this.addMoney_btn._visible = false;
         this.addMoney_txt._visible = false;
         this.paymentGold_btn._visible = true;
      }
   }
   function free()
   {
      clearInterval(this.timer);
      lol.core.SceneShifter.closeWindow("alert");
      this.resurrector.resurrect(lol.gpui.RegenerationInterface.RESURECT_FREE);
   }
   function payGold()
   {
      var _loc3_ = lol.core.Master.getInstance().gamer.attributes.gold;
      var _loc2_;
      if(_loc3_ < this.GOLD_COST)
      {
         _loc2_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc2_.content.label = "У вас недостаточно золота";
      }
      else
      {
         clearInterval(this.timer);
         this.resurrector.resurrect(lol.gpui.RegenerationInterface.RESURECT_GOLD);
      }
   }
   function payAfro()
   {
      var _loc3_ = lol.core.Master.getInstance().gamer.attributes.afro;
      var _loc2_;
      if(_loc3_ < 500)
      {
         _loc2_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc2_.content.label = "У вас недостаточно денег";
      }
      else
      {
         clearInterval(this.timer);
         this.resurrector.resurrect(lol.gpui.RegenerationInterface.RESURECT_AFRO);
      }
   }
   function addMoney()
   {
      var _loc2_ = lol.core.SceneShifter._ref.getProfileUrl();
      this.getURL(_loc2_,"_blank");
   }
   function resurrect(obj)
   {
      var _loc2_ = obj.success;
      if(!_loc2_)
      {
         clearInterval(this.timer);
         this.timer = setInterval(this,"checkTimePause",1000);
      }
   }
   function startTimer()
   {
      this.currentTime = 0;
      this.timer_txt.text = this.timePause + " сек.";
      clearInterval(this.timer);
      this.timer = setInterval(this,"checkTimePause",1000);
   }
   function checkTimePause()
   {
      this.currentTime = this.currentTime + 1;
      if(this.currentTime >= this.timePause)
      {
         clearInterval(this.timer);
         this.free();
      }
      var _loc3_ = this.timePause - this.currentTime;
      var _loc2_ = new TextFormat();
      _loc2_.bold = true;
      this.timer_txt.text = _loc3_ + " сек.";
      this.timer_txt.setTextFormat(_loc2_);
   }
}
