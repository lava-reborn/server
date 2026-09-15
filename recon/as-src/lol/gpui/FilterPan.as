class lol.gpui.FilterPan extends lol.gpui.GPUIObject
{
   var btn0;
   var btn1;
   var btn2;
   var btn3;
   var btn4;
   var btn5;
   var btn6;
   var btn7;
   var btn8;
   var btn9;
   var dispatchEvent;
   var sortMask;
   var filterNum = 10;
   function FilterPan()
   {
      super();
   }
   function init(_sortMask)
   {
      this.sortMask = new Array();
      this.sortMask = _sortMask;
      var _loc2_ = 0;
      while(_loc2_ < this.filterNum)
      {
         if(this.sortMask[_loc2_])
         {
            this["btn" + _loc2_].toggled = true;
         }
         this["btn" + _loc2_].hintInstance = "filter_btn_" + _loc2_;
         this["btn" + _loc2_].data = _loc2_;
         this["btn" + _loc2_].addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortClick);
         _loc2_ = _loc2_ + 1;
      }
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER0,this,this.filter0);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER1,this,this.filter1);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER2,this,this.filter2);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER3,this,this.filter3);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER4,this,this.filter4);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER5,this,this.filter5);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER6,this,this.filter6);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER7,this,this.filter7);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER8,this,this.filter8);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER9,this,this.filter9);
      this.btn0.hintTitle_str = "Фильтровать по оружию";
      this.btn1.hintTitle_str = "Фильтровать по одежде";
      this.btn2.hintTitle_str = "Фильтровать по восстанавливающим средствам";
      this.btn3.hintTitle_str = "Фильтровать по патронам";
      this.btn4.hintTitle_str = "Фильтровать по остальным предметам";
      this.btn5.hintTitle_str = "Фильтровать по холодному оружию";
      this.btn6.hintTitle_str = "Фильтровать по трофеям";
      this.btn7.hintTitle_str = "Фильтровать по квестовым предметам";
      this.btn8.hintTitle_str = "Доступность по цене";
      this.btn9.hintTitle_str = "Доступность по уровню";
   }
   function sortMaskToggled(sm)
   {
      this.sortMask = sm;
      var _loc2_ = 0;
      while(_loc2_ < this.filterNum)
      {
         if(this.sortMask[_loc2_])
         {
            this["btn" + _loc2_].toggled = true;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function kill()
   {
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER0,this,this.filter0);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER1,this,this.filter1);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER2,this,this.filter2);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER3,this,this.filter3);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER4,this,this.filter4);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER5,this,this.filter5);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER6,this,this.filter6);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER7,this,this.filter7);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER8,this,this.filter8);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER9,this,this.filter9);
      var _loc2_ = 0;
      while(_loc2_ < this.filterNum)
      {
         this["btn" + _loc2_].removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortClick);
         _loc2_ = _loc2_ + 1;
      }
   }
   function filter0()
   {
      this.btn0.toggled = !this.btn0.toggled;
      this._sortClick(this.btn0);
   }
   function filter1()
   {
      this.btn1.toggled = !this.btn1.toggled;
      this._sortClick(this.btn1);
   }
   function filter2()
   {
      this.btn2.toggled = !this.btn2.toggled;
      this._sortClick(this.btn2);
   }
   function filter3()
   {
      this.btn3.toggled = !this.btn3.toggled;
      this._sortClick(this.btn3);
   }
   function filter4()
   {
      this.btn4.toggled = !this.btn4.toggled;
      this._sortClick(this.btn4);
   }
   function filter5()
   {
      this.btn5.toggled = !this.btn5.toggled;
      this._sortClick(this.btn5);
   }
   function filter6()
   {
      this.btn6.toggled = !this.btn6.toggled;
      this._sortClick(this.btn6);
   }
   function filter7()
   {
      this.btn7.toggled = !this.btn7.toggled;
      this._sortClick(this.btn7);
   }
   function filter8()
   {
      this.btn8.toggled = !this.btn8.toggled;
      this._sortClick(this.btn8);
   }
   function filter9()
   {
      this.btn9.toggled = !this.btn9.toggled;
      this._sortClick(this.btn9);
   }
   function _sortClick(btn)
   {
      var _loc2_ = btn.data;
      this.sortMask[_loc2_] = btn.toggled;
      this.dispatchEvent({type:"changeMask",sortMask:this.sortMask});
   }
   function sortClick(obj)
   {
      var _loc2_ = obj.target;
      this._sortClick(_loc2_);
   }
   function changeMask(obj)
   {
      var _loc2_ = 0;
      while(_loc2_ < this.sortMask.length)
      {
         this["btn" + _loc2_].toggled = this.sortMask[_loc2_];
         _loc2_ = _loc2_ + 1;
      }
   }
}
