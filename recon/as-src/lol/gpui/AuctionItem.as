class lol.gpui.AuctionItem extends lol.gpui.GPUIObject
{
   var _xmouse;
   var _ymouse;
   var bg_btn;
   var buyout_txt;
   var count_txt;
   var dispatchEvent;
   var doLater;
   var item;
   var itemCont;
   var lot;
   var name_txt;
   var player_txt;
   var rate_txt;
   var tf;
   var time_txt;
   static var RATE_RELEASE = "RATE_RELEASE";
   static var BUYOUT_RELEASE = "BUYOUT_RELEASE";
   static var SELECT_ITEM = "SELECT_ITEM";
   var myLot = false;
   var itemW = 134;
   var itemH = 27;
   var selected = false;
   function AuctionItem()
   {
      super();
      this.doLater("init");
      this.tf = new TextFormat();
      this.tf.bold = true;
   }
   function init()
   {
      this.bg_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this.bgOver);
      this.bg_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT,this,this.bgOut);
      this.bg_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.bgOut);
      this.bg_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectItem);
   }
   function kill()
   {
      this.lot.removeEventListener(lol.core.objects.Lot.LOT_UPDATE,this,this.lotUpdate);
      this.bg_btn.removeEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this.bgOver);
      this.bg_btn.removeEventListener(lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT,this,this.bgOut);
      this.bg_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.bgOut);
      this.bg_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectItem);
   }
   function initByLot(_lot, _myLot)
   {
      this.lot = _lot;
      this.myLot = _myLot;
      this.setName(this.lot.name);
      this.setCount(this.lot.count);
      this.setTime(this.lot.time + " ч");
      if(this.myLot)
      {
         this.setPlayerName(this.lot.bidder);
      }
      else
      {
         this.setPlayerName(this.lot.playerName);
      }
      this.setItem(this.lot.item);
      if(this.lot.rateACost || this.lot.buyoutACost)
      {
         this.setRateCost(this.lot.rateACost + " А");
         if(this.lot.buyoutACost > 0)
         {
            this.setBuyoutCost(this.lot.buyoutACost + " А");
         }
         else
         {
            this.setBuyoutCost("нет");
         }
      }
      else if(this.lot.rateGCost || this.lot.buyoutGCost)
      {
         this.setRateCost(this.lot.rateGCost / 100 + " G");
         if(this.lot.buyoutGCost > 0)
         {
            this.setBuyoutCost(this.lot.buyoutGCost / 100 + " G");
         }
         else
         {
            this.setBuyoutCost("нет");
         }
      }
      this.lot.addEventListener(lol.core.objects.Lot.LOT_UPDATE,this,this.lotUpdate);
   }
   function lotUpdate()
   {
      this.setName(this.lot.name);
      this.setCount(this.lot.count);
   }
   function setName(value)
   {
      this.name_txt.text = value.toUpperCase();
      this.name_txt.setTextFormat(this.tf);
   }
   function setCount(value)
   {
      this.count_txt.text = String(value);
      this.count_txt.setTextFormat(this.tf);
   }
   function setTime(value)
   {
      this.time_txt.text = value;
      this.time_txt.setTextFormat(this.tf);
   }
   function setPlayerName(value)
   {
      this.player_txt.text = value;
      this.player_txt.setTextFormat(this.tf);
   }
   function setRateCost(value)
   {
      this.rate_txt.text = value;
      this.rate_txt.setTextFormat(this.tf);
   }
   function setBuyoutCost(value)
   {
      this.buyout_txt.text = value;
      this.buyout_txt.setTextFormat(this.tf);
   }
   function setItem(value)
   {
      this.item = value;
   }
   function getItem()
   {
      return this.item;
   }
   function rate()
   {
      this.dispatchEvent({type:lol.gpui.AuctionItem.RATE_RELEASE});
   }
   function buyout()
   {
      this.dispatchEvent({type:lol.gpui.AuctionItem.BUYOUT_RELEASE});
   }
   function bgOver()
   {
      this.bg_btn.toggled = true;
      this.createAnnotation();
   }
   function bgOut()
   {
      if(!this.selected)
      {
         this.bg_btn.toggled = false;
      }
      this.deleteAnnotation();
   }
   function selectItem()
   {
      this.selected = true;
      this.bg_btn.toggled = true;
      this.dispatchEvent({type:lol.gpui.AuctionItem.SELECT_ITEM});
   }
   function select()
   {
      this.selected = true;
      this.bg_btn.toggled = true;
   }
   function unselect()
   {
      this.selected = false;
      this.bg_btn.toggled = false;
   }
   function createAnnotation()
   {
      lol.gpui.AnnotationManager.clear();
      lol.gpui.AnnotationManager.create(this.item,this._xmouse,this.itemW + 166 - this._xmouse,this._ymouse - this.itemH);
      var _loc2_ = lol.core.SceneShifter.linkWindow;
      this.itemCont = lol.gpui.ItemContainer(_loc2_.attachMovie("itemCont","itemCont",_loc2_.getNextHighestDepth()));
      this.itemCont.item = this.item;
      this.itemCont.attachIcon(this.item);
      this.itemCont._x = _loc2_._xmouse + this.itemW - this._xmouse;
      this.itemCont._y = _loc2_._ymouse + this.itemH - this._ymouse;
   }
   function deleteAnnotation()
   {
      this.itemCont.kill();
      this.itemCont.removeMovieClip();
      lol.gpui.AnnotationManager.clear();
   }
}
