class lol.services.HotKeyManager
{
   var dispatchEvent;
   var hotKeyArr;
   var hotKeyFilter_arr;
   var hotKeyFilters;
   var keyPressStack;
   var keyStack;
   static var __enabled = true;
   var m = 0;
   function HotKeyManager()
   {
      var _loc2_ = new lol.utils.Timeout(this,this.init,500);
   }
   function init()
   {
      lol.events.LEventDispatcher.initialize(this);
      Key.addListener(this);
      this.createArr();
      this.keyPressStack = new Array();
      this.keyStack = new Array();
      this.hotKeyFilters = new lol.services.HotKeyFilter();
   }
   function createArr()
   {
      this.hotKeyArr = new Array();
      this.createDefaultArr();
      var _loc2_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.HOT_KEYS);
      if(_loc2_)
      {
         for(var _loc3_ in this.hotKeyArr)
         {
            if(_loc2_[_loc3_])
            {
               delete this.hotKeyArr[_loc3_];
               this.hotKeyArr[_loc3_] = _loc2_[_loc3_];
            }
         }
      }
      this.resort();
   }
   function addFilter(str)
   {
      if(!this.hotKeyFilter_arr)
      {
         this.hotKeyFilter_arr = new Array();
      }
      if(this.hotKeyFilter_arr[this.hotKeyFilter_arr.length - 1] != str)
      {
         this.hotKeyFilter_arr.push(str);
      }
   }
   function removeFilter(str)
   {
      var _loc3_;
      var _loc2_ = 0;
      while(_loc2_ < this.hotKeyFilter_arr.length)
      {
         if(this.hotKeyFilter_arr[_loc2_] == str)
         {
            _loc3_ = _loc2_;
            this.hotKeyFilter_arr.splice(_loc2_,1);
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function createDefaultArr()
   {
      if(!this.hotKeyArr)
      {
         this.hotKeyArr = new Array();
      }
      this.hotKeyArr[lol.services.HotKeyEvent.APPLY] = {keyCode:[13],keyCode1:[13],focus:true,about:""};
      this.hotKeyArr[lol.services.HotKeyEvent.CANCEL] = {keyCode:[27],keyCode1:[27],focus:true,about:""};
      this.hotKeyArr[lol.services.HotKeyEvent.HAND_SCROLL] = {keyCode:[16],keyCode1:[16],focus:true,about:""};
      this.hotKeyArr[lol.services.HotKeyEvent.SCROLL_UP] = {keyCode:[87],keyCode1:[38],focus:true,title:"Локация",about:"Прокрутить локацию вверх"};
      this.hotKeyArr[lol.services.HotKeyEvent.SCROLL_DOWN] = {keyCode:[83],keyCode1:[40],focus:true,title:"Локация",about:"Прокрутить локацию вниз"};
      this.hotKeyArr[lol.services.HotKeyEvent.SCROLL_LEFT] = {keyCode:[65],keyCode1:[37],focus:true,title:"Локация",about:"Прокрутить локацию влево"};
      this.hotKeyArr[lol.services.HotKeyEvent.SCROLL_RIGHT] = {keyCode:[68],keyCode1:[39],focus:true,title:"Локация",about:"Прокрутить локацию вправо"};
      this.hotKeyArr[lol.services.HotKeyEvent.MINI_MAP] = {keyCode:[77],keyCode1:[16,77],focus:true,title:"Локация",about:"Открыть/закрыть мини-карту"};
      this.hotKeyArr[lol.services.HotKeyEvent.WEAPON_PAN] = {keyCode:[69],keyCode1:[16,69],focus:true,title:"Локация",about:"Открыть/закрыть панель оружия"};
      this.hotKeyArr[lol.services.HotKeyEvent.CHANGE_WEAPON] = {keyCode:[81],keyCode1:[16,81],focus:true,title:"Локация",about:"Сменить активный слот"};
      this.hotKeyArr[lol.services.HotKeyEvent.CHANGE_WORLD] = {keyCode:[16,13],keyCode1:[16,13],focus:true,title:"Локация",about:"Перейти на глобальную карту"};
      this.hotKeyArr[lol.services.HotKeyEvent.RELOAD] = {keyCode:[82],keyCode1:[16,82],focus:true,title:"Локация",about:"Перезарядить оружие"};
      this.hotKeyArr[lol.services.HotKeyEvent.CENTER_ON_CHAR] = {keyCode:[67],keyCode1:[36],focus:true,title:"Локация",about:"Центрировать на персонаже"};
      this.hotKeyArr[lol.services.HotKeyEvent.PERS_INFO] = {keyCode:[80],keyCode1:[16,80],focus:true,title:"Локация",about:"Информация о персонаже"};
      this.hotKeyArr[lol.services.HotKeyEvent.EQUIPMENT] = {keyCode:[73],keyCode1:[16,73],focus:true,title:"Локация",about:"Открыть инвентарь"};
      this.hotKeyArr[lol.services.HotKeyEvent.HEAL] = {keyCode:[72],keyCode1:[16,72],focus:true,title:"Локация",about:"Восстановить здоровье"};
      this.hotKeyArr[lol.services.HotKeyEvent.EAT] = {keyCode:[70],keyCode1:[16,70],focus:true,title:"Локация",about:"Восстановить силы"};
      this.hotKeyArr[lol.services.HotKeyEvent.FILTER0] = {keyCode:[49],keyCode1:[16,49],focus:true,title:"Работа с рюкзаком",about:"Фильтрация по оружию"};
      this.hotKeyArr[lol.services.HotKeyEvent.FILTER1] = {keyCode:[50],keyCode1:[16,50],focus:true,title:"Работа с рюкзаком",about:"Фильтрация по одежде"};
      this.hotKeyArr[lol.services.HotKeyEvent.FILTER2] = {keyCode:[51],keyCode1:[16,51],focus:true,title:"Работа с рюкзаком",about:"Фильтрация по аптечке"};
      this.hotKeyArr[lol.services.HotKeyEvent.FILTER3] = {keyCode:[52],keyCode1:[16,52],focus:true,title:"Работа с рюкзаком",about:"Фильтрация по патронам"};
      this.hotKeyArr[lol.services.HotKeyEvent.FILTER4] = {keyCode:[53],keyCode1:[16,53],focus:true,title:"Работа с рюкзаком",about:"Фильтрация по трэшу"};
      this.hotKeyArr[lol.services.HotKeyEvent.FILTER5] = {keyCode:[54],keyCode1:[16,54],focus:true,title:"Работа с рюкзаком",about:"Фильтрация по ножам"};
      this.hotKeyArr[lol.services.HotKeyEvent.FILTER6] = {keyCode:[55],keyCode1:[16,55],focus:true,title:"Работа с рюкзаком",about:"Фильтрация по трофеям"};
      this.hotKeyArr[lol.services.HotKeyEvent.FILTER7] = {keyCode:[56],keyCode1:[16,56],focus:true,title:"Работа с рюкзаком",about:"Фильтрация по квестовым предметам"};
      this.hotKeyArr[lol.services.HotKeyEvent.FIRE_MODE0] = {keyCode:[49],keyCode1:[16,49],focus:true,title:"Локация",about:"Режим стрельбы 1"};
      this.hotKeyArr[lol.services.HotKeyEvent.FIRE_MODE1] = {keyCode:[50],keyCode1:[16,50],focus:true,title:"Локация",about:"Режим стрельбы 2"};
      this.hotKeyArr[lol.services.HotKeyEvent.FIRE_MODE2] = {keyCode:[51],keyCode1:[16,51],focus:true,title:"Локация",about:"Режим стрельбы 3"};
      this.hotKeyArr[lol.services.HotKeyEvent.SELECT_ALL] = {keyCode:[17,65],keyCode1:[17,65],focus:true,title:"Работа с рюкзаком",about:"Выделить все объекты"};
      this.hotKeyArr[lol.services.HotKeyEvent.COPY_LOG] = {keyCode:[32,67],keyCode1:[32,67],focus:true,title:"",about:""};
      this.hotKeyArr[lol.services.HotKeyEvent.SCALE_UP] = {keyCode:[107],keyCode1:[187],focus:true,title:"Глобальная карта",about:"Увеличить карту"};
      this.hotKeyArr[lol.services.HotKeyEvent.SCALE_DOWN] = {keyCode:[109],keyCode1:[189],focus:true,title:"Глобальная карта",about:"Уменьшить карту"};
      this.hotKeyArr[lol.services.HotKeyEvent.GRID] = {keyCode:[90],keyCode1:[16,90],focus:true,title:"Глобальная карта",about:"Включить/выключить сетку"};
      this.hotKeyArr[lol.services.HotKeyEvent.SETTINGS] = {keyCode:[78],keyCode1:[16,78],focus:true,title:"Общие",about:"Открыть/закрыть панель настроек"};
      this.hotKeyArr[lol.services.HotKeyEvent.CHAT_IN_FOCUS] = {keyCode:[13],keyCode1:[13],focus:true,title:"Общие",about:"Установить фокус в окне ввода чата"};
      this.hotKeyArr[lol.services.HotKeyEvent.SPACE] = {keyCode:[32],keyCode1:[16,32],focus:true,title:"Общие",about:"Действие"};
      this.hotKeyArr[lol.services.HotKeyEvent.ESC] = {keyCode:[27],keyCode1:[27],focus:false,about:""};
      this.hotKeyArr[lol.services.HotKeyEvent.BACKSPACE] = {keyCode:[8],keyCode1:[16,8],focus:true,about:""};
      this.hotKeyArr[lol.services.HotKeyEvent.CTRL] = {keyCode:[17],keyCode1:[17],focus:true,about:""};
      this.hotKeyArr[lol.services.HotKeyEvent.SHIFT] = {keyCode:[16],keyCode1:[16],focus:true,about:""};
      this.hotKeyArr[lol.services.HotKeyEvent.RETURN_OLD_NAME] = {keyCode:[38],keyCode1:[38],focus:false,about:""};
   }
   function set enabled(value)
   {
      lol.services.HotKeyManager.__enabled = value;
   }
   function get enabled()
   {
      return lol.services.HotKeyManager.__enabled;
   }
   function enabledHotKey(str, b)
   {
      this.hotKeyArr[str].__enabled = b;
   }
   function saveSettings()
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.HOT_KEYS,this.hotKeyArr);
   }
   function getKeyInfo(str)
   {
      return this.hotKeyArr[str];
   }
   function getHotKeyArr()
   {
      this.hotKeyArr.sortOn(["title"]);
      return this.hotKeyArr;
   }
   function keyPress(code)
   {
      var _loc3_ = "code" + String(code);
      this.keyPressStack[_loc3_] = code;
      this.keyStack.push(code);
      this.checkHotKey("");
   }
   function keyRelease(code)
   {
      var _loc4_ = "code" + String(code);
      delete this.keyPressStack[_loc4_];
      for(var _loc3_ in this.keyStack)
      {
         if(this.keyStack[_loc3_] == code)
         {
            this.keyStack.splice(Number(_loc3_),1);
         }
      }
   }
   function checkHotKey(str)
   {
      var _loc16_ = new Array();
      var _loc4_ = new Object();
      var _loc15_ = 0;
      var _loc7_;
      var _loc3_;
      var _loc5_;
      var _loc11_;
      var _loc8_;
      var _loc2_;
      while(_loc15_ < this.keyStack.length)
      {
         _loc7_ = this.keyStack[_loc15_];
         for(var _loc12_ in this.hotKeyArr)
         {
            if(_loc4_[_loc12_] || _loc15_ == 0)
            {
               _loc3_ = this.hotKeyArr[_loc12_];
               _loc5_ = false;
               _loc2_ = this.m;
               while(_loc2_ < _loc3_["keyCode" + str].length)
               {
                  if(_loc3_["keyCode" + str][_loc2_] == _loc7_)
                  {
                     _loc5_ = true;
                     _loc8_ = _loc2_;
                  }
                  _loc2_ = _loc2_ + 1;
               }
               if(_loc5_)
               {
                  _loc4_[_loc12_] = [_loc15_,_loc12_];
               }
               else
               {
                  delete _loc4_[_loc12_];
               }
            }
         }
         _loc15_ = _loc15_ + 1;
      }
      var _loc13_ = 0;
      var _loc9_;
      var _loc14_;
      var _loc10_ = false;
      for(_loc15_ in _loc4_)
      {
         _loc13_ = _loc13_ + 1;
         _loc14_ = _loc4_[_loc15_][0];
         _loc9_ = _loc4_[_loc15_][1];
         _loc10_ = this.hotKeyArr[_loc9_]["keyCode" + str].length == this.keyStack.length;
         if(_loc10_)
         {
            this.checkAndDispatch(_loc9_);
         }
      }
   }
   function checkAndDispatch(title)
   {
      var _loc2_;
      if(this.enabled || !this.hotKeyArr[title].focus)
      {
         _loc2_ = this.hotKeyFilters.getFilter(this.hotKeyFilter_arr[this.hotKeyFilter_arr.length - 1]);
         for(var _loc5_ in _loc2_)
         {
            if(_loc2_[_loc5_] == title)
            {
               this.dispatchEvent({type:title});
               break;
            }
         }
      }
   }
   function onKeyDown()
   {
      var _loc3_ = Key.getCode();
      var _loc2_ = "code" + String(_loc3_);
      if(!this.keyPressStack[_loc2_])
      {
         this.keyPress(_loc3_);
      }
      this.dispatchEvent({type:lol.services.HotKeyEvent.KEY_PRESS,code:_loc3_});
   }
   function onKeyUp()
   {
      var _loc2_ = Key.getCode();
      this.keyRelease(_loc2_);
      this.dispatchEvent({type:lol.services.HotKeyEvent.KEY_RELEASE,code:_loc2_});
   }
   function resort()
   {
      this.hotKeyArr.sortOn(["title"]);
   }
   function checkFilter(str)
   {
      return this.hotKeyFilter_arr[this.hotKeyFilter_arr.length - 1] == str;
   }
}
