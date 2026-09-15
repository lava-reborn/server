class lol.gpui.AuctionInterface extends lol.gpui.StaffInterface
{
   var auction;
   var auctionPan;
   var buyout_btn;
   var category_dropList;
   var close_btn;
   var costAEnd_txt;
   var costAStart_txt;
   var costGEnd_txt;
   var costGStart_txt;
   var count;
   var currSort_btn;
   var dispatchEvent;
   var doLater;
   var gamer;
   var itemArr;
   var levelEnd_txt;
   var levelStart_txt;
   var master;
   var moneyPan_afro;
   var moneyPan_gold;
   var name_txt;
   var next;
   var next_btn;
   var page;
   var prev_btn;
   var prev_rate;
   var rate_afro_mc;
   var rate_btn;
   var rate_gold_mc;
   var rate_txt;
   var searchObj;
   var search_btn;
   var selectItem;
   var sortByCost_btn;
   var sortByCount_btn;
   var sortByMaster_btn;
   var sortByName_btn;
   var sortByTime_btn;
   var type_dropList;
   var itemCount = 0;
   var RATE_PERCENT = 0.1;
   var tooOftenFlag = false;
   var searchEnabled = true;
   function AuctionInterface()
   {
      super();
      this.doLater("init");
      this.master = lol.core.Master.getInstance();
      this.gamer = this.master.gamer;
      this.auction = this.gamer.auction;
      this.next_btn._visible = false;
      this.prev_btn._visible = false;
   }
   function init()
   {
      this.moneyPan_afro.type = "afro";
      this.moneyPan_afro.setPlayer(this.gamer);
      this.moneyPan_gold.type = "gold";
      this.moneyPan_gold.setPlayer(this.gamer);
      this.auctionPan.fillContent();
      this.auctionPan.setSize(428,319);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.auction.typeOfAuc = 0;
      this.auction.addEventListener(lol.core.player.Auction.ADD_LOT,this,this.addLot);
      this.auction.addEventListener(lol.core.player.Auction.SEARCH_RESULT,this,this.searchResult);
      this.auction.addEventListener(lol.core.player.Auction.TOO_OFTEN,this,this.tooOften);
      this.category_dropList.addEventListener(lol.gpui.controls.DropList.CHANGED,this,this.changedCategory);
      this.search_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.search);
      this.sortByName_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByCount_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByTime_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByMaster_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByCost_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.prev_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.prevPage);
      this.next_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.nextPage);
      this.rate_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.rateLot);
      this.buyout_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.buyoutLot);
      this.category_dropList.setSize(199,136);
      this.category_dropList.addItem("Любая",-1,true);
      this.category_dropList.addItem("Огнестрельное оружие",lol.core.objects.Item.FIRE_ARM);
      this.category_dropList.addItem("Холодное оружие",lol.core.objects.Item.COLD_ARM);
      this.category_dropList.addItem("Боеприпасы",lol.core.objects.Item.AMMO);
      this.category_dropList.addItem("Одежда",lol.core.objects.Item.WEAR);
      this.category_dropList.addItem("Лечащие предметы",lol.core.objects.Item.HEAL_ITEM);
      this.category_dropList.addItem("Разное",lol.core.objects.Item.TRASH);
      this.category_dropList.addItem("Трофеи",lol.core.objects.Item.TROPHY);
      this.type_dropList.addItem("",-1,true);
      this.type_dropList.enabled = false;
      this.levelStart_txt.restrict = "0-9";
      this.levelEnd_txt.restrict = "0-9";
      this.costAStart_txt.restrict = "0-9";
      this.costGStart_txt.restrict = "0-9.";
      this.costAEnd_txt.restrict = "0-9";
      this.costGEnd_txt.restrict = "0-9.";
      this.name_txt.tabIndex = 0;
      this.levelStart_txt.tabIndex = 1;
      this.levelEnd_txt.tabIndex = 2;
      this.costAStart_txt.tabIndex = 3;
      this.costAEnd_txt.tabIndex = 4;
      this.costGStart_txt.tabIndex = 5;
      this.costGEnd_txt.tabIndex = 6;
      this.rate_txt.onChanged = mx.utils.Delegate.create(this,this.check_rate_txt);
      this.currSort_btn = this.sortByName_btn;
      this.currSort_btn.setFrame(lol.gpui.controls.SortButton.SORT_UP_FRAME);
      this.clearAuctionPan();
      lol.core.SceneShifter.locationScreen.centerChar();
      lol.core.SceneShifter.hotKeyManager.addFilter("auction");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.ESC,this,this.close);
   }
   function kill()
   {
      this.clearAuctionPan();
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.auction.removeEventListener(lol.core.player.Auction.ADD_LOT,this,this.addLot);
      this.auction.removeEventListener(lol.core.player.Auction.SEARCH_RESULT,this,this.searchResult);
      this.auction.removeEventListener(lol.core.player.Auction.TOO_OFTEN,this,this.tooOften);
      this.category_dropList.removeEventListener(lol.gpui.controls.DropList.CHANGED,this,this.changedCategory);
      this.search_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.search);
      this.sortByName_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByCount_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByTime_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByMaster_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByCost_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.prev_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.prevPage);
      this.next_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.nextPage);
      this.rate_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.rateLot);
      this.buyout_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.buyoutLot);
      lol.core.SceneShifter.hotKeyManager.removeFilter("auction");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.ESC,this,this.close);
      this.moneyPan_afro.kill();
      this.moneyPan_gold.kill();
      super.kill();
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function changedCategory(obj)
   {
      var _loc2_ = this.category_dropList.curItem.data;
      this.type_dropList.enabled = true;
      this.type_dropList.removeAll();
      switch(_loc2_)
      {
         case -1:
            this.type_dropList.addItem("",-1,true);
            this.type_dropList.enabled = false;
            break;
         case 0:
            this.type_dropList.addItem("Любой",-1,true);
            this.type_dropList.addItem("Пистолеты",0);
            this.type_dropList.addItem("Дробовики",1);
            this.type_dropList.addItem("Автоматы",2);
            this.type_dropList.addItem("Винтовки",3);
            this.type_dropList.addItem("Пулемёты",4);
            this.type_dropList.addItem("Пистолеты-пулемёты",5);
            this.type_dropList.addItem("Остальное",6);
            this.type_dropList.setSize(199,136);
            break;
         case 1:
            this.type_dropList.addItem("Любой",-1,true);
            this.type_dropList.addItem("Голова",0);
            this.type_dropList.addItem("Грудь",1);
            this.type_dropList.addItem("Броня",2);
            this.type_dropList.addItem("Ноги",4);
            this.type_dropList.addItem("Ступни",5);
            this.type_dropList.setSize(199,102);
            break;
         case 2:
            this.type_dropList.addItem("Любой",-1,true);
            this.type_dropList.addItem("Восстановление здоровья",0);
            this.type_dropList.addItem("Восстановление выносливости",1);
            this.type_dropList.setSize(199,51);
            break;
         case 3:
            this.type_dropList.addItem("Любой",-1,true);
            this.type_dropList.addItem("5.56x45",0);
            this.type_dropList.addItem("7.62x25",1);
            this.type_dropList.addItem("7.62x39",2);
            this.type_dropList.addItem("7.62x51",3);
            this.type_dropList.addItem("7.62x54R",4);
            this.type_dropList.addItem("9mm",5);
            this.type_dropList.addItem("0.45",6);
            this.type_dropList.addItem("12 cal",7);
            this.type_dropList.addItem("Остальное",8);
            this.type_dropList.setSize(199,170);
            break;
         case 4:
            this.type_dropList.addItem("Любой",-1,true);
            this.type_dropList.addItem("Детали",1);
            this.type_dropList.addItem("Чертежи",2);
            this.type_dropList.addItem("Предметы для заданий",3);
            this.type_dropList.addItem("Остальное",0);
            this.type_dropList.setSize(199,85);
            break;
         case 5:
            this.type_dropList.addItem("",-1,true);
            this.type_dropList.enabled = false;
            break;
         case 6:
            this.type_dropList.addItem("",-1,true);
            this.type_dropList.enabled = false;
            break;
         case 100:
            this.type_dropList.addItem("",-1,true);
            this.type_dropList.enabled = false;
         default:
            return;
      }
   }
   function tooOften(obj)
   {
      this.tooOftenFlag = obj.value;
      if(obj.value)
      {
         if(this.page == 0)
         {
            this.prev_btn.enabled = false;
         }
         else
         {
            this.prev_btn.enabled = true;
         }
         if(this.next == 0)
         {
            this.next_btn.enabled = false;
         }
         else
         {
            this.next_btn.enabled = true;
            this.next_btn._visible = true;
            this.prev_btn._visible = true;
         }
         if(this.next == 0 && this.page == 0)
         {
            this.next_btn._visible = false;
            this.prev_btn._visible = false;
         }
         this.search_btn.enabled = true;
         this.sortByName_btn.enabled = true;
         this.sortByCount_btn.enabled = true;
         this.sortByTime_btn.enabled = true;
         this.sortByMaster_btn.enabled = true;
         this.sortByCost_btn.enabled = true;
      }
      else
      {
         this.search_btn.enabled = false;
         this.next_btn.enabled = false;
         this.prev_btn.enabled = false;
         this.sortByName_btn.enabled = false;
         this.sortByCount_btn.enabled = false;
         this.sortByTime_btn.enabled = false;
         this.sortByMaster_btn.enabled = false;
         this.sortByCost_btn.enabled = false;
      }
   }
   function addLot(obj)
   {
      var _loc6_ = lol.core.objects.Lot(obj.lot);
      var _loc3_ = this.auctionPan.content;
      var _loc5_ = _loc3_.getNextHighestDepth();
      var _loc4_;
      if(this.itemCount % 2 == 0)
      {
         _loc4_ = "auctionItem";
      }
      else
      {
         _loc4_ = "auctionItem_2";
      }
      var _loc2_ = lol.gpui.AuctionItem(_loc3_.attachMovie(_loc4_,"auctionItem" + this.itemCount,_loc5_));
      _loc2_.addEventListener(lol.gpui.AuctionItem.SELECT_ITEM,this,this.select);
      _loc2_.initByLot(_loc6_);
      _loc2_._y = this.itemCount * 29;
      this.itemCount = this.itemCount + 1;
      this.itemArr.push(_loc2_);
      this.auctionPan.chekSize();
      this.auctionPan.setPosition(0,0);
   }
   function searchResult(obj)
   {
      this.clearAuctionPan();
      this.page = obj.page;
      this.count = obj.count;
      this.next = obj.next;
      if(this.tooOftenFlag)
      {
         if(this.page == 0)
         {
            this.prev_btn.enabled = false;
         }
         else
         {
            this.prev_btn.enabled = true;
         }
         if(this.next == 0)
         {
            this.next_btn.enabled = false;
         }
         else
         {
            this.next_btn.enabled = true;
            this.next_btn._visible = true;
            this.prev_btn._visible = true;
         }
         if(this.next == 0 && this.page == 0)
         {
            this.next_btn._visible = false;
            this.prev_btn._visible = false;
         }
      }
      if(this.count == 0)
      {
         this.createInfo("Ничего не найдено");
      }
   }
   function search()
   {
      if(this.name_txt.text.length >= 3)
      {
         this.searchObj = this.getSearchObject();
         this._search();
      }
      else if(this.name_txt.text)
      {
         this.createAlert("Поле название должно содержать не менее 3 символов");
      }
      else
      {
         this.searchObj = this.getSearchObject();
         this._search();
      }
   }
   function _search()
   {
      this.createInfo("Идёт поиск");
      this.auction.search(this.searchObj);
   }
   function searchEnabledFunc()
   {
      this.searchEnabled = true;
   }
   function sortOn(obj)
   {
      var _loc2_ = lol.gpui.controls.SortButton(obj.target);
      if(this.currSort_btn != _loc2_)
      {
         this.currSort_btn.setFrame(lol.gpui.controls.SortButton.STATIC_FRAME);
         this.currSort_btn = _loc2_;
      }
      if(this.itemCount)
      {
         this.searchObj.sortBy = this.getSortBy().sort;
         this.searchObj.sortByMode = this.getSortBy().s_mode;
         this._search();
      }
   }
   function clearAuctionPan()
   {
      for(var _loc2_ in this.itemArr)
      {
         lol.gpui.AuctionItem(this.itemArr[_loc2_]).removeEventListener(lol.gpui.AuctionItem.SELECT_ITEM,this,this.select);
         lol.gpui.AuctionItem(this.itemArr[_loc2_]).kill();
         lol.gpui.AuctionItem(this.itemArr[_loc2_]).removeMovieClip();
      }
      this.itemArr = new Array();
      this.auctionPan.fillContent();
      this.itemCount = 0;
      delete this.selectItem;
      this.rate_btn.enabled = false;
      this.buyout_btn.enabled = false;
      this.rate_txt.text = "";
      this.rate_txt._visible = false;
      this.rate_afro_mc._visible = false;
      this.rate_gold_mc._visible = false;
   }
   function rateLot(obj)
   {
      var _loc4_ = !this.rate_txt.text ? 0 : Number(this.rate_txt.text);
      var _loc3_;
      var _loc2_;
      if(_loc4_ >= this.selectItem.lot.rateACost * (1 + this.RATE_PERCENT) || _loc4_ * 100 >= this.selectItem.lot.rateGCost * (1 + this.RATE_PERCENT))
      {
         _loc3_ = Number(this.rate_txt.text);
         if(this.selectItem.lot.rateGCost)
         {
            _loc3_ = Math.floor(_loc3_ * 100);
         }
         this.auction.addEventListener(lol.core.player.Auction.BID_RESULT,this,this.rateLotAck);
         this.auction.rateLot(this.selectItem.lot.item.id,_loc3_);
      }
      else
      {
         _loc2_ = "Ваша ставка меньше минимально допустимой. Минимально допустимая ставка: ";
         if(this.selectItem.lot.rateGCost)
         {
            _loc2_ += this.selectItem.lot.rateGCost / 100 * (1 + this.RATE_PERCENT) + " G";
         }
         else
         {
            _loc2_ += this.selectItem.lot.rateACost * (1 + this.RATE_PERCENT) + " A";
         }
         this.createAlert(_loc2_);
      }
   }
   function rateLotAck(obj)
   {
      this.auction.removeEventListener(lol.core.player.Auction.BID_RESULT,this,this.rateLotAck);
      if(obj.res == 0)
      {
         this.createAlert("Ваша ставка принята");
      }
      else if(obj.res == 40)
      {
         this.createAlert("Лот не найден");
      }
      else if(obj.res == 9)
      {
         this.createAlert("Ставка слишком низка. Возможно кто-то уже сделал более высокую ставку");
      }
      else
      {
         this.createAlert("У вас недостаточно денег");
      }
   }
   function buyoutLot(obj)
   {
      var _loc2_ = lol.gpui.dialogue.GPUIDialogue(lol.core.SceneShifter.openNewWindow("query").content);
      if(this.selectItem.lot.buyoutACost)
      {
         _loc2_.label = "Купить предмет\r&lt;" + this.selectItem.lot.name + "&gt;\r за " + this.selectItem.lot.buyoutACost + " Афро?";
      }
      else if(this.selectItem.lot.buyoutGCost)
      {
         _loc2_.label = "Купить предмет\r&lt;" + this.selectItem.lot.name + "&gt;\r за " + this.selectItem.lot.buyoutGCost / 100 + " унций золота?";
      }
      _loc2_.addEventListener("click",this,this._buyoutLot);
   }
   function _buyoutLot(obj)
   {
      obj.target.removeEventListener("click",this,this._buyoutLot);
      lol.core.SceneShifter.closeWindow("query");
      if(obj.success)
      {
         this.auction.addEventListener(lol.core.player.Auction.BUYOUT_RESULT,this,this.buyoutLotAck);
         this.auction.buyoutLot(this.selectItem.lot.item.id);
      }
   }
   function buyoutLotAck(obj)
   {
      this.auction.removeEventListener(lol.core.player.Auction.BID_RESULT,this,this.buyoutLotAck);
      if(obj.res == 0)
      {
         this.createAlert("Товар выкуплен");
      }
      else if(obj.res == 40)
      {
         this.createAlert("Лот не найден");
      }
      else
      {
         this.createAlert("У вас недостаточно денег");
      }
   }
   function check_rate_txt()
   {
      var _loc2_;
      if(this.rate_txt.text == "")
      {
         this.prev_rate = "";
      }
      else
      {
         _loc2_ = Number(this.rate_txt.text);
         if(_loc2_ || _loc2_ == 0)
         {
            this.prev_rate = _loc2_;
         }
         else
         {
            this.rate_txt.text = this.prev_rate;
         }
      }
      if(this.rate_txt.text == "" || Number(this.rate_txt.text) < this.selectItem.lot.rateACost || Number(this.rate_txt.text) * 100 < this.selectItem.lot.rateGCost)
      {
         this.rate_btn.enabled = false;
      }
      else
      {
         this.rate_btn.enabled = true;
      }
   }
   function prevPage(obj)
   {
      this.createInfo("Идёт поиск");
      this.auction.prevPage();
   }
   function nextPage(obj)
   {
      this.createInfo("Идёт поиск");
      this.auction.nextPage();
   }
   function select(obj)
   {
      if(lol.gpui.AuctionItem(obj.target) != this.selectItem)
      {
         this.selectItem.unselect();
         this.selectItem = lol.gpui.AuctionItem(obj.target);
         if(this.selectItem.lot.rateACost || this.selectItem.lot.rateGCost)
         {
            this.rate_btn.enabled = true;
            this.rate_txt._visible = true;
            if(this.selectItem.lot.rateACost)
            {
               this.rate_txt.restrict = "0-9";
               this.rate_afro_mc._visible = true;
               this.rate_gold_mc._visible = false;
               this.rate_txt.text = String(Math.ceil(this.selectItem.lot.rateACost * (1 + this.RATE_PERCENT)));
            }
            else if(this.selectItem.lot.rateGCost)
            {
               this.rate_txt.restrict = "0-9.";
               this.rate_afro_mc._visible = false;
               this.rate_gold_mc._visible = true;
               this.rate_txt.text = String(Math.ceil(this.selectItem.lot.rateGCost * (1 + this.RATE_PERCENT)) / 100);
            }
            this.check_rate_txt();
         }
         if(this.selectItem.lot.buyoutACost || this.selectItem.lot.buyoutGCost)
         {
            this.buyout_btn.enabled = true;
            if(this.selectItem.lot.rateACost && this.selectItem.lot.rateACost >= this.selectItem.lot.buyoutACost)
            {
               this.rate_btn.enabled = false;
               this.rate_txt._visible = false;
            }
            else if(this.selectItem.lot.rateGCost && this.selectItem.lot.rateGCost >= this.selectItem.lot.buyoutGCost)
            {
               this.rate_btn.enabled = false;
               this.rate_txt._visible = false;
            }
         }
      }
   }
   function createInfo(str)
   {
      var _loc2_ = this.auctionPan.fillContent("auc_info_mc");
      _loc2_.info_txt.text = str;
      var _loc3_ = new TextFormat();
      _loc3_.bold = true;
      _loc2_.info_txt.setTextFormat(_loc3_);
      this.auctionPan.chekSize();
   }
   function createAlert(str)
   {
      var _loc1_ = lol.gpui.dialogue.GPUIAlert(lol.core.SceneShifter.openNewWindow("alert").content);
      _loc1_.label = str;
   }
   function getSearchObject()
   {
      var _loc2_ = new Object();
      _loc2_.name = !this.name_txt.text ? "" : this.name_txt.text;
      _loc2_.category = this.category_dropList.curItem.data;
      _loc2_.type = this.type_dropList.curItem.data;
      _loc2_.min_level = !this.levelStart_txt.text ? 0 : Number(this.levelStart_txt.text);
      _loc2_.max_level = !this.levelEnd_txt.text ? 0 : Number(this.levelEnd_txt.text);
      _loc2_.min_aCost = !this.costAStart_txt.text ? 0 : Number(this.costAStart_txt.text);
      _loc2_.max_aCost = !this.costAEnd_txt.text ? 0 : Number(this.costAEnd_txt.text);
      _loc2_.min_gCost = !Number(this.costGStart_txt.text) ? 0 : Math.floor(Number(this.costGStart_txt.text) * 100);
      _loc2_.max_gCost = !Number(this.costGEnd_txt.text) ? 0 : Math.floor(Number(this.costGEnd_txt.text) * 100);
      _loc2_.sortBy = this.getSortBy().sort;
      _loc2_.sortByMode = this.getSortBy().s_mode;
      return _loc2_;
   }
   function getSortBy()
   {
      var _loc2_ = new Object();
      switch(this.currSort_btn)
      {
         case this.sortByName_btn:
            _loc2_.sort = 0;
            break;
         case this.sortByCount_btn:
            _loc2_.sort = 1;
            break;
         case this.sortByTime_btn:
            _loc2_.sort = 2;
            break;
         case this.sortByMaster_btn:
            _loc2_.sort = 3;
            break;
         case this.sortByCost_btn:
            _loc2_.sort = 4;
      }
      if(this.currSort_btn.currentState == lol.gpui.controls.SortButton.SORT_DOWN_FRAME)
      {
         _loc2_.s_mode = 0;
      }
      else
      {
         _loc2_.s_mode = 1;
      }
      return _loc2_;
   }
}
