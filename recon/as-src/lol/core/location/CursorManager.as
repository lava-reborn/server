class lol.core.location.CursorManager
{
   var CTRLisDown;
   var addEventListener;
   var core_mc;
   var currentCursor;
   var dispatchEvent;
   var distance_txt;
   var exitTimer;
   var helpers_mc;
   var lastCell;
   var lastMode;
   var master;
   var removeEventListener;
   var selectRect;
   var selected;
   var sfManager;
   var target;
   var targetList;
   var tf;
   static var inited;
   static var itemActionMap;
   static var targetActionMap;
   static var SELECT = "select";
   static var MOVE = "move";
   static var TRANSPORT = "transport";
   static var FIRE = "fire";
   static var FIRE_HEX = "fireHex";
   static var TAKE = "take";
   static var HEAL = "heal";
   static var USE_ITEM = "useItem";
   static var ACTIVE = "contact";
   static var STRIKE = "strike";
   static var STRIKE_HEX = "strikeHex";
   function CursorManager(targ)
   {
      this.master = lol.core.Master.getInstance();
      this.target = targ;
      this.core_mc = this.target.core_mc;
      this.helpers_mc = this.target.helpers_mc;
      this.tf = new TextFormat();
      this.tf.font = "Tahoma";
      this.tf.align = "left";
      this.tf.size = 9;
      var _loc2_ = new flash.filters.GlowFilter(0,100,3,3,4,1);
      this.distance_txt = this.helpers_mc.createTextField("distance_txt",this.helpers_mc.getNextHighestDepth(),0,0,100,20);
      this.distance_txt.textColor = 16777215;
      this.distance_txt.antiAliasType = "advanced";
      this.distance_txt.embedFonts = true;
      this.distance_txt.setTextFormat(this.tf);
      this.distance_txt.filters = [_loc2_];
      lol.events.LEventDispatcher.initialize(this);
      this.sfManager = new lol.display.SpriteFocusManager();
      this.sfManager.addEventListener(lol.display.SpriteFocus.onSpriteClick,this);
      this.sfManager.addEventListener(lol.display.SpriteFocus.onSpriteOver,this);
      this.sfManager.activate(true);
      this.cursorMode(lol.core.location.CursorManager.MOVE);
      if(!lol.core.location.CursorManager.inited)
      {
         lol.core.location.CursorManager.initialize();
      }
      Key.addListener(this);
      Mouse.addListener(this);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.SPACE,this,this.spacePress);
      this.targetList = new lol.core.location.TargetList();
      this.targetList.addEventListener("change",this,this.changeTargetHandler);
      lol.core.Master.getInstance().gamer.walker.addEventListener("finishPart",this,this.calcDistance);
      this.addEventListener("select",this.master.gamer.contactManager,this.master.gamer.contactManager.selectPlayer);
   }
   function escPress()
   {
   }
   function addFocus(targ, focusTarg, runtime)
   {
      var _loc2_ = new lol.display.SpriteFocus(targ,focusTarg,runtime);
      this.sfManager.addFocus(_loc2_);
   }
   function removeFocus(targ)
   {
      this.targetList.removeTarget(targ.id);
      if(this.selected == this.sfManager.getFocus(targ))
      {
         this.selected = null;
         this.dispatchEvent({type:"select",id:null});
         this.targetList.nextTarget();
      }
      this.sfManager.removeFocus(targ);
   }
   function spriteOver(obj)
   {
      var _loc2_;
      if(Key.isDown(17))
      {
         _loc2_ = this.forceMode(this.sfManager.flared);
         this.cursorMode(_loc2_);
      }
      else
      {
         _loc2_ = this.normalMode();
         this.cursorMode(_loc2_);
         if(obj.flared != null)
         {
            this.dispatchEvent({type:"spriteOver",flared:obj.flared});
         }
         else
         {
            this.dispatchEvent({type:"spriteOut"});
         }
      }
   }
   function spriteClick(obj)
   {
      if(!Key.isDown(17))
      {
      }
   }
   function __onMouseUp()
   {
      var _loc2_ = this.sfManager.flared;
      var _loc3_;
      if(!this.selectRect.rectFlag && !Key.isDown(17))
      {
         if(_loc2_ && this.selected && _loc2_ == this.selected)
         {
            _loc3_ = this.forceMode(_loc2_);
            this.applyAction(_loc3_,[_loc2_]);
         }
         else
         {
            _loc3_ = this.normalMode();
            this.applyAction(_loc3_,[_loc2_]);
         }
      }
      this.selectRect._onMouseUp();
   }
   function __onMouseDown()
   {
      var _loc2_ = this.sfManager.flared;
      var _loc3_;
      this.selectRect = new lol.services.SelectionRect(this.target);
      this.selectRect._onMouseDown();
      if(Key.isDown(17))
      {
         _loc3_ = this.forceMode(this.sfManager.flared);
         this.applyAction(_loc3_,[_loc2_]);
         if(this.normalMode() == lol.core.location.CursorManager.SELECT)
         {
            this.select();
         }
      }
   }
   function spacePress()
   {
      var _loc2_;
      if(this.selected)
      {
         _loc2_ = this.forceMode(this.selected);
         this.applyAction(_loc2_,[this.selected]);
      }
   }
   function onKeyDown()
   {
      var _loc4_;
      var _loc2_;
      var _loc3_;
      if(Key.isDown(17))
      {
         if(!this.CTRLisDown)
         {
            this.CTRLisDown = true;
            _loc4_ = this.forceMode(this.sfManager.flared);
            this.cursorMode(_loc4_);
         }
      }
      else if(Key.isDown(9))
      {
         _loc2_ = this.target.playerList;
         _loc3_ = this.getPrioritySelectionTarget(_loc2_);
         this.select(_loc3_);
      }
   }
   function onKeyUp()
   {
      this.CTRLisDown = Key.isDown(17);
      var _loc2_ = this.normalMode();
      this.cursorMode(_loc2_);
   }
   function activate(status)
   {
      if(status)
      {
         this.target.bg_mc.onRelease = this.target.bg_mc.onReleaseOutside = mx.utils.Delegate.create(this,this.__onMouseUp);
         this.target.bg_mc.onPress = mx.utils.Delegate.create(this,this.__onMouseDown);
         this.cursorMode(lol.core.location.CursorManager.MOVE);
         this.sfManager.activate(true);
      }
      else
      {
         delete this.target.onPress;
         this.removeCurrentCursor();
         this.lastMode = null;
         this.sfManager.activate(false);
      }
   }
   function activateFocus(target, a)
   {
      var _loc2_ = this.sfManager.getFocus(target);
      _loc2_.activate(a);
   }
   function removeCurrentCursor()
   {
      this.currentCursor.onMouseMove.target = null;
      this.currentCursor.onMouseMove.func = null;
      delete this.currentCursor.onMouseMove;
      delete this.currentCursor.onPress;
      this.currentCursor.removeMovieClip();
   }
   function moveUsualCursor()
   {
      this.currentCursor._x = this.target._xmouse;
      this.currentCursor._y = this.target._ymouse;
      this.calcDistance();
   }
   function moveHexCursor()
   {
      var _loc2_ = this.target.getCellFromReal(this.target._xmouse,this.target._ymouse);
      this.target.placeObject(this.currentCursor,_loc2_.rx,_loc2_.ry);
      if(_loc2_.zone)
      {
         if(!this.exitTimer)
         {
            this.exitTimerNum();
            this.exitTimer = setInterval(this,"exitTimerNum",400);
         }
      }
      else if(this.exitTimer)
      {
         this.currentCursor.exitTimer_txt.text = "";
         clearInterval(this.exitTimer);
         delete this.exitTimer;
      }
      if(_loc2_ != this.lastCell)
      {
         this.calcDistance();
         this.lastCell = _loc2_;
         this.target.showCollision(this.currentCursor._x,this.currentCursor._y);
         this.checkHex(_loc2_);
      }
   }
   function exitTimerNum()
   {
      this.currentCursor.exitTimer_txt.text = !lol.core.SceneShifter.locationScreen.exitTime ? "" : lol.core.SceneShifter.locationScreen.exitTime;
   }
   function cursorMode(mode)
   {
      if(mode != this.lastMode)
      {
         this.lastMode = mode;
         this.removeCurrentCursor();
         switch(mode)
         {
            case lol.core.location.CursorManager.SELECT:
               this.selectCMode();
               return;
            case lol.core.location.CursorManager.MOVE:
               this.moveCMode();
               return;
            case lol.core.location.CursorManager.FIRE:
               this.fireCMode();
               return;
            case lol.core.location.CursorManager.FIRE_HEX:
               this.fireHexCMode();
               return;
            case lol.core.location.CursorManager.TAKE:
               this.useCMode();
               return;
            case lol.core.location.CursorManager.ACTIVE:
               this.contactCMode();
               return;
            case lol.core.location.CursorManager.TRANSPORT:
               this.trnasportCMode();
               return;
            case lol.core.location.CursorManager.USE_ITEM:
               this.useItemCMode();
               return;
            case lol.core.location.CursorManager.HEAL:
               this.useItemCMode();
               return;
            default:
               this.moveCMode();
               return;
         }
      }
   }
   function selectCMode()
   {
      this.currentCursor = this.helpers_mc.attachMovie("selectCursor","selectCursor",this.helpers_mc.getNextHighestDepth());
      this.currentCursor.onMouseMove = mx.utils.Delegate.create(this,this.moveUsualCursor);
      this.moveUsualCursor();
   }
   function moveCMode()
   {
      this.currentCursor = this.core_mc.attachMovie("hexCursor","hexCursor",0);
      this.currentCursor.onMouseMove = mx.utils.Delegate.create(this,this.moveHexCursor);
      this.moveHexCursor();
   }
   function useCMode()
   {
      this.currentCursor = this.helpers_mc.attachMovie("useCursor","useCursor",this.helpers_mc.getNextHighestDepth());
      this.currentCursor.onMouseMove = mx.utils.Delegate.create(this,this.moveUsualCursor);
      this.moveUsualCursor();
   }
   function contactCMode()
   {
      this.currentCursor = this.helpers_mc.attachMovie("contactCursor","contactCursor",this.helpers_mc.getNextHighestDepth());
      this.currentCursor.onMouseMove = mx.utils.Delegate.create(this,this.moveUsualCursor);
      this.moveUsualCursor();
   }
   function trnasportCMode()
   {
      this.currentCursor = this.helpers_mc.attachMovie("transportCursor","transportCursor",this.helpers_mc.getNextHighestDepth());
      this.currentCursor.onMouseMove = mx.utils.Delegate.create(this,this.moveUsualCursor);
      this.moveUsualCursor();
   }
   function useItemCMode()
   {
      this.currentCursor = this.helpers_mc.attachMovie("useItemCursor","useItemCursor",this.helpers_mc.getNextHighestDepth());
      this.currentCursor.onMouseMove = mx.utils.Delegate.create(this,this.moveUsualCursor);
      this.moveUsualCursor();
   }
   function fireCMode()
   {
      this.currentCursor = this.helpers_mc.attachMovie("fireCursor","fireCursor",this.helpers_mc.getNextHighestDepth());
      this.currentCursor.onMouseMove = mx.utils.Delegate.create(this,this.moveUsualCursor);
      this.moveUsualCursor();
   }
   function fireHexCMode()
   {
      this.currentCursor = this.helpers_mc.attachMovie("fireHexCursor","fireHexCursor",this.helpers_mc.getNextHighestDepth());
      this.currentCursor.onMouseMove = mx.utils.Delegate.create(this,this.moveUsualCursor);
      this.moveUsualCursor();
   }
   function normalMode(spriteFocus)
   {
      var _loc3_ = !spriteFocus ? this.sfManager.flared : spriteFocus;
      var _loc2_;
      var _loc4_;
      var _loc5_;
      if(_loc3_)
      {
         _loc4_ = _loc3_.target.driver;
         _loc5_ = this.getClassFunc(_loc4_);
         if(this.checkDriver())
         {
            _loc2_ = _loc5_.staticID;
         }
         else
         {
            _loc2_ = 0;
         }
      }
      else
      {
         _loc2_ = lol.core.location.HexCell.staticID;
      }
      var _loc6_ = lol.core.location.CursorManager.targetActionMap[_loc2_];
      return _loc6_;
   }
   function forceMode(spriteFocus)
   {
      var _loc2_;
      var _loc4_;
      var _loc5_;
      if(spriteFocus)
      {
         _loc4_ = spriteFocus.target.driver;
         _loc5_ = this.getClassFunc(_loc4_);
         _loc2_ = _loc5_.staticID;
      }
      else
      {
         _loc2_ = lol.core.location.HexCell.staticID;
      }
      var _loc3_;
      var _loc7_ = lol.core.Master.getInstance().gamer.equipment.primaryItem;
      _loc3_ = _loc7_.rootID;
      var _loc6_ = lol.core.location.CursorManager.itemActionMap[_loc3_][_loc2_];
      return _loc6_;
   }
   function applyAction(mode, args)
   {
      var _loc2_ = this[mode];
      _loc2_.apply(this,args);
   }
   function move()
   {
      var _loc2_ = this.target.getCellFromReal(this.target._xmouse,this.target._ymouse);
      this.target.movePlayer(_loc2_);
      this.master.gamer.clearTask();
   }
   function fire(spriteFocus)
   {
      var _loc2_ = spriteFocus.target.driver.id;
      this.master.gamer.fire(1,_loc2_);
      this.target.currentLocation.fireUser(_loc2_);
   }
   function fireHex()
   {
      var _loc2_ = this.target.getCellFromReal(this.target._xmouse,this.target._ymouse);
      this.master.currentLocation.fireHex(_loc2_.num);
      this.master.gamer.fire(0,_loc2_.num);
   }
   function select(spriteFocus)
   {
      var _loc2_ = !spriteFocus ? this.sfManager.flared : spriteFocus;
      var _loc5_;
      var _loc3_;
      if(this.selected)
      {
         _loc5_ = this.selected.target.driver.id;
         _loc3_ = this.target.helperObjects[_loc5_];
         _loc3_.autoAim(false);
         this.selected.target.filters = new Array();
      }
      this.selected = _loc2_;
      _loc5_ = this.selected.target.driver.id;
      _loc3_ = this.target.helperObjects[_loc5_];
      _loc3_.autoAim(true);
      var _loc4_;
      if(this.selected)
      {
         _loc4_ = new flash.filters.GlowFilter(16645995,100,3,3,4,1);
         this.selected.target.filters = new Array(_loc4_);
      }
      this.targetList.addTarget(_loc5_);
      this.dispatchEvent({type:"select",id:_loc5_});
   }
   function take()
   {
      var _loc2_ = this.sfManager.flared.target.driver.id;
      this.master.gamer.gotoLoot(_loc2_);
   }
   function contact(spriteFocus)
   {
      var _loc2_ = spriteFocus.target.driver.id;
      this.master.gamer.gotoWalker(_loc2_,"contact");
   }
   function transport(spriteFocus)
   {
      var _loc2_ = spriteFocus.target.driver.id;
      this.master.gamer.gotoWalker(_loc2_,"contact");
   }
   function heal(spriteFocus)
   {
      var _loc2_ = spriteFocus.target.driver.id;
      this.master.gamer.gotoWalker(_loc2_,"heal");
   }
   function strike(spriteFocus)
   {
      var _loc2_ = spriteFocus.target.driver.id;
      this.master.gamer.gotoWalker(_loc2_,"strike");
   }
   function strikeHex()
   {
      var _loc2_ = this.target.getCellFromReal(this.target._xmouse,this.target._ymouse);
      this.master.gamer.strikeHex(_loc2_.num);
   }
   function getClassFunc(obj)
   {
      var _loc1_;
      if(obj instanceof lol.core.player.Player)
      {
         if(obj instanceof lol.core.player.Gamer)
         {
            _loc1_ = lol.core.player.Gamer;
         }
         else
         {
            _loc1_ = lol.core.player.Player;
         }
      }
      else if(obj instanceof lol.core.player.Mob)
      {
         _loc1_ = lol.core.player.Mob;
      }
      else if(obj instanceof lol.core.player.Trader)
      {
         _loc1_ = lol.core.player.Trader;
      }
      else if(obj instanceof lol.core.player.Auctioner)
      {
         _loc1_ = lol.core.player.Auctioner;
      }
      else if(obj instanceof lol.core.player.Teacher)
      {
         _loc1_ = lol.core.player.Teacher;
      }
      else if(obj instanceof lol.core.player.Upgrader)
      {
         _loc1_ = lol.core.player.Upgrader;
      }
      else if(obj instanceof lol.core.player.Lessor)
      {
         _loc1_ = lol.core.player.Lessor;
      }
      else if(obj instanceof lol.core.player.Commoner)
      {
         _loc1_ = lol.core.player.Commoner;
      }
      else if(obj instanceof lol.core.player.Healer)
      {
         _loc1_ = lol.core.player.Healer;
      }
      else if(obj instanceof lol.core.location.LootBag)
      {
         _loc1_ = lol.core.location.LootBag;
      }
      return _loc1_;
   }
   function checkDriver(driver)
   {
      var _loc1_ = true;
      return _loc1_;
   }
   static function initialize()
   {
      lol.core.location.CursorManager.targetActionMap = new Array();
      lol.core.location.CursorManager.targetActionMap[lol.core.player.Gamer.staticID] = null;
      lol.core.location.CursorManager.targetActionMap[lol.core.player.Player.staticID] = lol.core.location.CursorManager.SELECT;
      lol.core.location.CursorManager.targetActionMap[lol.core.player.Mob.staticID] = lol.core.location.CursorManager.SELECT;
      lol.core.location.CursorManager.targetActionMap[lol.core.player.Trader.staticID] = lol.core.location.CursorManager.ACTIVE;
      lol.core.location.CursorManager.targetActionMap[lol.core.player.Auctioner.staticID] = lol.core.location.CursorManager.ACTIVE;
      lol.core.location.CursorManager.targetActionMap[lol.core.player.Teacher.staticID] = lol.core.location.CursorManager.ACTIVE;
      lol.core.location.CursorManager.targetActionMap[lol.core.player.Upgrader.staticID] = lol.core.location.CursorManager.ACTIVE;
      lol.core.location.CursorManager.targetActionMap[lol.core.player.Commoner.staticID] = lol.core.location.CursorManager.ACTIVE;
      lol.core.location.CursorManager.targetActionMap[lol.core.player.Healer.staticID] = lol.core.location.CursorManager.ACTIVE;
      lol.core.location.CursorManager.targetActionMap[lol.core.location.LootBag.staticID] = lol.core.location.CursorManager.TAKE;
      lol.core.location.CursorManager.targetActionMap[lol.core.location.HexCell.staticID] = lol.core.location.CursorManager.MOVE;
      lol.core.location.CursorManager.targetActionMap[lol.core.player.Lessor.staticID] = lol.core.location.CursorManager.TRANSPORT;
      lol.core.location.CursorManager.itemActionMap = new Array();
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM] = new Array();
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM][lol.core.player.Gamer.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM][lol.core.player.Player.staticID] = lol.core.location.CursorManager.FIRE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM][lol.core.player.Mob.staticID] = lol.core.location.CursorManager.FIRE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM][lol.core.player.Trader.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM][lol.core.player.Commoner.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM][lol.core.player.Healer.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM][lol.core.player.Teacher.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM][lol.core.player.Upgrader.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM][lol.core.location.LootBag.staticID] = lol.core.location.CursorManager.FIRE_HEX;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIRE_ARM][lol.core.location.HexCell.staticID] = lol.core.location.CursorManager.FIRE_HEX;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM] = new Array();
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM][lol.core.player.Gamer.staticID] = lol.core.location.CursorManager.HEAL;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM][lol.core.player.Player.staticID] = lol.core.location.CursorManager.HEAL;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM][lol.core.player.Mob.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM][lol.core.player.Trader.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM][lol.core.player.Commoner.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM][lol.core.player.Healer.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM][lol.core.player.Teacher.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM][lol.core.player.Upgrader.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM][lol.core.location.LootBag.staticID] = lol.core.location.CursorManager.TAKE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.HEAL_ITEM][lol.core.location.HexCell.staticID] = lol.core.location.CursorManager.MOVE;
      lol.core.location.CursorManager.itemActionMap.fist = new Array();
      lol.core.location.CursorManager.itemActionMap.fist[lol.core.player.Gamer.staticID] = null;
      lol.core.location.CursorManager.itemActionMap.fist[lol.core.player.Player.staticID] = lol.core.location.CursorManager.STRIKE;
      lol.core.location.CursorManager.itemActionMap.fist[lol.core.player.Mob.staticID] = lol.core.location.CursorManager.STRIKE;
      lol.core.location.CursorManager.itemActionMap.fist[lol.core.player.Trader.staticID] = null;
      lol.core.location.CursorManager.itemActionMap.fist[lol.core.player.Teacher.staticID] = null;
      lol.core.location.CursorManager.itemActionMap.fist[lol.core.player.Upgrader.staticID] = null;
      lol.core.location.CursorManager.itemActionMap.fist[lol.core.player.Commoner.staticID] = null;
      lol.core.location.CursorManager.itemActionMap.fist[lol.core.player.Healer.staticID] = null;
      lol.core.location.CursorManager.itemActionMap.fist[lol.core.location.LootBag.staticID] = lol.core.location.CursorManager.TAKE;
      lol.core.location.CursorManager.itemActionMap.fist[lol.core.location.HexCell.staticID] = lol.core.location.CursorManager.MOVE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST] = new Array();
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST][lol.core.player.Gamer.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST][lol.core.player.Player.staticID] = lol.core.location.CursorManager.STRIKE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST][lol.core.player.Mob.staticID] = lol.core.location.CursorManager.STRIKE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST][lol.core.player.Trader.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST][lol.core.player.Teacher.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST][lol.core.player.Upgrader.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST][lol.core.player.Commoner.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST][lol.core.player.Healer.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST][lol.core.location.LootBag.staticID] = lol.core.location.CursorManager.TAKE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.FIST][lol.core.location.HexCell.staticID] = lol.core.location.CursorManager.MOVE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM] = new Array();
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM][lol.core.player.Gamer.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM][lol.core.player.Player.staticID] = lol.core.location.CursorManager.STRIKE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM][lol.core.player.Mob.staticID] = lol.core.location.CursorManager.STRIKE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM][lol.core.player.Trader.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM][lol.core.player.Commoner.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM][lol.core.player.Teacher.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM][lol.core.player.Upgrader.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM][lol.core.player.Healer.staticID] = null;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM][lol.core.location.LootBag.staticID] = lol.core.location.CursorManager.TAKE;
      lol.core.location.CursorManager.itemActionMap[lol.core.objects.Item.COLD_ARM][lol.core.location.HexCell.staticID] = lol.core.location.CursorManager.STRIKE_HEX;
   }
   function calcDistance()
   {
      var _loc7_ = this.currentCursor._x;
      var _loc6_ = this.currentCursor._y;
      this.distance_txt._x = _loc7_ + 20;
      this.distance_txt._y = _loc6_ - 6;
      var _loc11_ = this.target.master.gamer.walker.numPos;
      var _loc12_ = this.target.master.currentLocation.getCellFromNumber(_loc11_);
      var _loc5_;
      var _loc9_;
      var _loc10_;
      if(this.sfManager.flared)
      {
         _loc9_ = this.sfManager.flared.target.id;
         _loc10_ = this.target.master.currentLocation.getWalker(_loc9_).numPos;
         _loc5_ = this.target.master.currentLocation.getCellFromNumber(_loc10_);
      }
      else
      {
         _loc5_ = this.target.master.currentLocation.getCellFromReal(_loc7_,_loc6_);
      }
      var _loc2_ = 0.1 * Math.floor(10 * this.target.master.currentLocation.locationGrid.getHexDistance(_loc12_,_loc5_));
      var _loc3_;
      var _loc4_;
      var _loc13_;
      var _loc8_;
      var _loc14_;
      if(!isNaN(_loc2_))
      {
         this.distance_txt.text = _loc2_;
         if(lol.core.Master.getInstance().gamer.equipment.primaryItem instanceof lol.core.objects.FireArm)
         {
            _loc3_ = lol.core.objects.FireArm(lol.core.Master.getInstance().gamer.equipment.primaryItem);
            _loc4_ = !_loc3_.getProp("cur_mode") ? 0 : _loc3_.getProp("cur_mode");
            _loc13_ = _loc3_.maxRange[_loc4_];
            _loc8_ = _loc3_.getProp("opt_range")[_loc4_];
            _loc14_ = _loc3_.getProp("end_opt_range")[_loc4_];
            if(_loc2_ >= _loc8_ && _loc2_ <= _loc14_)
            {
               this.tf.color = 65280;
            }
            else if(_loc2_ <= _loc13_)
            {
               this.tf.color = 16777215;
            }
            else
            {
               this.tf.color = 16711680;
            }
         }
         else if(_loc2_ <= 1)
         {
            this.tf.color = 65280;
         }
         else
         {
            this.tf.color = 16711680;
         }
         this.distance_txt.setTextFormat(this.tf);
      }
      else
      {
         this.distance_txt.text = "";
      }
   }
   function checkHex(cell)
   {
      if(cell.unreachable)
      {
         this.currentCursor.gotoAndStop(2);
      }
      else
      {
         this.currentCursor.gotoAndStop(1);
      }
   }
   function selectPlayers(playersArr)
   {
      this.addToTargetList(playersArr);
      var _loc2_ = this.getPrioritySelectionTarget(playersArr);
      if(this.normalMode(_loc2_) == lol.core.location.CursorManager.SELECT)
      {
         this.select(_loc2_);
      }
   }
   function addToTargetList(playersArr)
   {
      var _loc3_;
      for(var _loc4_ in playersArr)
      {
         _loc3_ = this.sfManager.getFocus(playersArr[_loc4_]);
         if(this.normalMode(_loc3_) == lol.core.location.CursorManager.SELECT)
         {
            this.targetList.addTarget(playersArr[_loc4_].id);
         }
      }
   }
   function getPrioritySelectionTarget(playersArr)
   {
      var _loc4_;
      var _loc7_;
      var _loc12_ = this.target.master.gamer.walker.numPos;
      var _loc10_ = this.target.master.currentLocation.getCellFromNumber(_loc12_);
      var _loc9_;
      var _loc8_;
      var _loc2_;
      var _loc3_;
      var _loc5_;
      for(var _loc11_ in playersArr)
      {
         _loc4_ = this.sfManager.getFocus(playersArr[_loc11_]);
         if(this.normalMode(_loc4_) == lol.core.location.CursorManager.SELECT)
         {
            _loc5_ = lol.core.Master.getInstance();
            if(_loc5_)
            {
               if(!_loc5_.playerRegister.gamer.partyManager.inParty(playersArr[_loc11_].id))
               {
                  _loc9_ = this.target.master.getPlayer(playersArr[_loc11_].id).walker.numPos;
                  _loc8_ = this.target.master.currentLocation.getCellFromNumber(_loc9_);
                  _loc3_ = this.target.master.currentLocation.locationGrid.getHexDistance(_loc10_,_loc8_);
                  if(!_loc2_)
                  {
                     _loc2_ = _loc3_;
                     _loc7_ = _loc4_;
                  }
                  else if(_loc3_ < _loc2_)
                  {
                     _loc2_ = _loc3_;
                     _loc7_ = _loc4_;
                  }
               }
            }
         }
      }
      return _loc7_;
   }
   function changeTargetHandler(obj)
   {
      var _loc4_ = obj.targetID;
      var _loc2_ = this.target.getWalker(_loc4_);
      var _loc3_ = this.sfManager.getFocus(_loc2_);
      this.select(_loc3_);
   }
   function getSelectedID()
   {
      return this.selected.target.driver.id;
   }
   function kill()
   {
      this.sfManager.activate(false);
      this.sfManager.removeEventListener("spriteOver",this);
      this.sfManager.removeEventListener("spriteClick",this);
      this.targetList.removeEventListener("change",this,this.changeTargetHandler);
      this.sfManager.kill();
      this.sfManager = null;
      this.selected = null;
      Key.removeListener(this);
      Mouse.removeListener(this);
      this.removeEventListener("select",this.master.gamer.contactManager,this.master.gamer.contactManager.selectPlayer);
   }
}
