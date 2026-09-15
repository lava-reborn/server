class lol.gpui.BattleGroundInterface extends lol.gpui.GPUIObject
{
   var bg_manager;
   var bg_penalty;
   var bg_reputation;
   var dialogPan;
   var exitBG_btn;
   var exitQueue_btn;
   var infoPan;
   var joinToBG_btn;
   var selectedSize;
   var selectedType;
   var sizeList;
   var status_bg;
   var typeList;
   function BattleGroundInterface()
   {
      super();
      trace("BattleGroundInterface");
      this.doLater("init");
   }
   function init()
   {
      this.bg_manager = lol.core.battlegrounds.BattleGroundManager.getInstance();
      this.infoPan.fillContent();
      this.infoPan.setSize(295,150);
      this.typeList.setSize(250,150);
      this.sizeList.setSize(133,150);
      this.fillTypeList();
      this.fillSizeList();
      this.typeList.addEventListener("select",this,this.SelectTypeList);
      this.sizeList.addEventListener("select",this,this.SelectSizeList);
      var _loc4_ = lol.core.Master.getInstance();
      var _loc2_ = lol.core.Master.getInstance().gamer;
      this.bg_reputation.value.text = "Репутация за арену: " + _loc2_.reputations.battleground_reputation;
      this.bg_penalty.value.text = "Штрафы за арену: " + _loc2_.reputations.battleground_penalty;
      this.bg_manager.addEventListener(lol.core.battlegrounds.BattleGroundManager.BG_EVENT_BG_ANSWER,this,this.BattleGroundAnswer);
      this.bg_manager.addEventListener(lol.core.battlegrounds.BattleGroundManager.BG_EVENT_SERVER_INVITE_US,this,this.BG_ServerInviteUs);
      this.joinToBG_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.joinToBattleGround);
      this.exitQueue_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.exitFromQueue);
      this.exitBG_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.exitFromBattleGround);
      if(this.bg_manager.BG_Status == lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_IDLE)
      {
         this.joinToBG_btn._visible = true;
         this.joinToBG_btn.enabled = true;
      }
      else
      {
         this.joinToBG_btn._visible = false;
         this.joinToBG_btn.enabled = false;
      }
      var _loc3_;
      if(this.bg_manager.BG_Status == lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_QUEUE)
      {
         _loc3_ = "Вы стоите в очереди на поле боя. Тип поля боя: " + this.bg_manager.getNameBG_ByTypeID(this.bg_manager.BG_Type) + ", размер поля боя: " + this.bg_manager.BG_Size + "x" + this.bg_manager.BG_Size;
         this.status_bg.value.text = _loc3_;
         this.exitQueue_btn._visible = true;
         this.exitQueue_btn.enabled = true;
      }
      else
      {
         this.exitQueue_btn._visible = false;
         this.exitQueue_btn.enabled = false;
      }
      if(this.bg_manager.BG_Status == lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_INVITED)
      {
         this.exitQueue_btn._visible = true;
         this.exitQueue_btn.enabled = true;
      }
      if(this.bg_manager.BG_Status == lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_ON_INCOMPLETE_BG || this.bg_manager.BG_Status == lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_ON_COMPLETE_BG)
      {
         this.exitBG_btn._visible = true;
         this.exitBG_btn.enabled = true;
      }
      else
      {
         this.exitBG_btn._visible = false;
         this.exitBG_btn.enabled = false;
      }
   }
   function kill()
   {
      this.bg_manager.removeEventListener(lol.core.battlegrounds.BattleGroundManager.BG_EVENT_BG_ANSWER,this,this.BattleGroundAnswer);
      this.bg_manager.removeEventListener(lol.core.battlegrounds.BattleGroundManager.BG_EVENT_SERVER_INVITE_US,this,this.BG_ServerInviteUs);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.cancel);
      this.typeList.removeEventListener("select",this,this.SelectTypeList);
      this.sizeList.removeEventListener("select",this,this.SelectSizeList);
      this.joinToBG_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.joinToBattleGround);
      this.exitQueue_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.exitFromQueue);
   }
   function exitFromQueue(obj)
   {
      this.exitQueue_btn._visible = false;
      this.exitQueue_btn.enabled = false;
      this.joinToBG_btn._visible = true;
      this.joinToBG_btn.enabled = true;
      this.status_bg.value.text = "Вы вышли из очереди";
      this.bg_manager.exitFromQueue();
   }
   function exitFromBattleGround(obj)
   {
      this.exitQueue_btn._visible = false;
      this.exitQueue_btn.enabled = false;
      this.exitBG_btn._visible = false;
      this.exitBG_btn.enabled = false;
      this.joinToBG_btn._visible = true;
      this.joinToBG_btn.enabled = true;
      this.bg_manager.exitFromBattleGround(false);
   }
   function SelectTypeList(obj)
   {
      this.infoPan.content.removeMovieClip();
      this.infoPan.fillContent();
      trace("SelectTypeList obj.selectedItem.data = " + obj.selectedItem.data);
      this.selectedType = obj.selectedItem.data;
      var _loc2_ = this.infoPan.content.attachMovie("skillInfo_title_","skillInfo_title_",this.infoPan.content.getNextHighestDepth());
      _loc2_.txt.autoSize = true;
      _loc2_.txt.wordWrap = true;
      _loc2_.txt._width = 280;
      _loc2_.txt._height = 130;
      var _loc3_;
      if(description != "none")
      {
         _loc3_ = new TextFormat();
         _loc3_.bold = true;
         var description = this.bg_manager.getDescBG_ByTypeID(obj.selectedItem.data);
         _loc2_.txt.htmlText = description;
         _loc2_.txt.setTextFormat(_loc3_);
      }
      else
      {
         _loc2_.txt.text = "Для данного элемента нет описания";
      }
   }
   function SelectSizeList(obj)
   {
      trace("SelectSizeList obj.selectedItem.data = " + obj.selectedItem.data);
      this.selectedSize = obj.selectedItem.data;
   }
   function fillTypeList()
   {
      var _loc2_;
      var _loc3_;
      var _loc6_;
      for(var _loc7_ in this.bg_manager.currentTypes)
      {
         _loc2_ = this.bg_manager.currentTypes[_loc7_];
         _loc3_ = this.bg_manager.getNameBG_ByTypeID(_loc2_);
         trace("type = " + _loc2_ + ", title = " + _loc3_);
         _loc6_ = this.typeList.addItem({label:_loc3_,data:_loc2_});
      }
      this.typeList.selectedIndex = 0;
   }
   function fillSizeList()
   {
      var _loc3_ = 0;
      var _loc2_;
      var _loc4_;
      var _loc7_;
      while(_loc3_ < this.bg_manager.currentSizes.length)
      {
         _loc2_ = this.bg_manager.currentSizes[_loc3_];
         _loc4_ = String(_loc2_ + "x" + _loc2_);
         trace("title = " + _loc4_);
         _loc7_ = this.sizeList.addItem({label:_loc4_,data:_loc2_});
         _loc3_ = _loc3_ + 1;
      }
      this.sizeList.selectedIndex = 0;
   }
   function joinToBattleGround()
   {
      trace("selectedSize = " + this.selectedSize + ", selectedType = " + this.selectedType);
      var _loc2_;
      var _loc3_;
      if(this.selectedSize != undefined && this.selectedSize >= 1 && this.selectedType != undefined && this.selectedType >= 0)
      {
         this.bg_manager.goToBattleGround(this.selectedType,this.selectedSize);
      }
      else
      {
         _loc2_ = lol.core.SceneShifter.openNewAlert("topSimple");
         _loc2_.label = "Выберите тип поля боя и его размер";
         _loc3_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
      }
   }
   function BattleGroundAnswer(obj)
   {
      trace("BattleGroundAnswer -> obj.res = " + obj.res);
      var _loc2_;
      if(obj.res == 0)
      {
         _loc2_ = "Вы стоите в очереди на поле боя. Тип поля боя: " + this.bg_manager.getNameBG_ByTypeID(this.selectedType) + ", размер поля боя: " + this.selectedSize + "x" + this.selectedSize;
         trace("s = " + _loc2_);
         this.status_bg.value.text = _loc2_;
         this.exitQueue_btn.enabled = true;
         this.exitQueue_btn._visible = true;
         this.joinToBG_btn.enabled = false;
         this.joinToBG_btn._visible = false;
      }
      else
      {
         this.status_bg.value.text = "Произошла ошибка при постановке в очередь на поле боя";
      }
   }
   function BG_ServerInviteUs(obj)
   {
      trace("BG_ServerInviteUs!");
      this.dialogPan = lol.core.SceneShifter.openNewWindow("query");
      var _loc2_ = this.dialogPan.content;
      var _loc5_ = lol.core.Master.getInstance();
      var _loc3_ = lol.core.Master.getInstance().gamer;
      var _loc4_ = _loc3_.playerInfo;
      var _loc6_ = _loc4_.name;
      _loc2_.alert_txt.text = "Зайти на поле боя?";
      _loc2_.clickEvent = "proposeJoinBG";
      _loc2_.addEventListener("proposeJoinBG",this);
   }
   function proposeJoinBG(obj)
   {
      lol.core.SceneShifter.closeWindow("query");
      this.bg_manager.SayAnswerToServer(obj.success);
   }
   function cancel()
   {
      lol.core.SceneShifter._sl.closeWinBtn_func();
   }
   function close()
   {
      var _loc1_ = new Object();
      _loc1_.data = "char";
      lol.core.SceneShifter._ref.currentScene.openCloseSlideWindow(_loc1_);
   }
}
