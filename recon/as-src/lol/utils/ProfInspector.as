class lol.utils.ProfInspector extends lol.gpui.GPUIObject
{
   var _parent;
   var attention_btn;
   var bg_mc;
   var calc_btn;
   var cc_txt;
   var clear_btn;
   var from_txt;
   var output_txt;
   var processList;
   var refresh_btn;
   var scrBar;
   var subProcessList;
   var to_txt;
   var totalTime_txt;
   function ProfInspector()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      this.processList.setSize(180,300);
      this.subProcessList.setSize(180,300);
      this.processList.addEventListener("select",this);
      this.subProcessList.addEventListener("select",this);
      this.refresh_btn.label = "refresh";
      this.refresh_btn.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.refreshList);
      this.clear_btn.label = "clear";
      this.clear_btn.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.clearList);
      this.bg_mc.onPress = function()
      {
         this._parent.startDrag();
      };
      this.bg_mc.onRelease = this.bg_mc.onReleaseOutside = function()
      {
         this._parent.stopDrag();
      };
      this.scrBar.target = this.output_txt;
      this.scrBar.setSize(this.output_txt._height);
      lol.server.XMLConnection.getInstance().addEventListener("cclength",this);
      this.calc_btn.label = "calc";
      this.calc_btn.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.calc);
      this.attention_btn.label = "attention";
      this.attention_btn.clickEvent = "attention";
      this.attention_btn.addEventListener("attention",this);
   }
   function refreshList()
   {
      this.clearList();
      this.fillProcessList();
      this.totalTime_txt.text = "getTimer: " + String(lol.utils.ExtProfiler.getTotalTime()) + "         totalCallTime: " + String(lol.utils.ExtProfiler.getTotalCallTime());
   }
   function fillProcessList()
   {
      var _loc3_ = lol.utils.ExtProfiler.processArray;
      var _loc2_;
      var _loc4_;
      var _loc6_;
      for(var _loc7_ in _loc3_)
      {
         _loc2_ = _loc3_[_loc7_].all;
         _loc4_ = _loc2_.name + " : " + _loc2_.count + " / " + _loc2_.totalTime + " ms";
         _loc6_ = this.processList.addItem({label:_loc4_,data:_loc2_});
      }
   }
   function fillSubList(name)
   {
      this.subProcessList.clearList();
      var _loc3_ = lol.utils.ExtProfiler.processArray[name];
      var _loc2_;
      var _loc4_;
      var _loc6_;
      for(var _loc7_ in _loc3_)
      {
         if(_loc7_ != "all")
         {
            _loc2_ = _loc3_[_loc7_];
            _loc4_ = _loc2_.name + " : " + _loc2_.count + " / " + _loc2_.totalTime + " ms";
            _loc6_ = this.subProcessList.addItem({label:_loc4_,data:_loc2_});
         }
      }
   }
   function attention(obj)
   {
      var _loc8_ = obj.target.toggled;
      var _loc3_;
      var _loc2_;
      var _loc4_;
      var _loc6_;
      if(_loc8_)
      {
         this.clearList();
         this.output_txt.text = "";
         _loc3_ = lol.utils.ExtProfiler.attentionArray;
         for(var _loc7_ in _loc3_)
         {
            _loc2_ = _loc3_[_loc7_];
            _loc4_ = _loc2_.name;
            _loc6_ = this.subProcessList.addItem({label:_loc4_,data:_loc2_});
         }
      }
      else
      {
         this.refreshList();
      }
   }
   function showProcess(process)
   {
      this.output_txt.text = "";
      this.output_txt.text += process.pname + " " + process.name + "  " + process.count + "\r\n";
      var _loc5_ = process.callArray.length >= 200 ? process.callArray.length - 200 : 0;
      var _loc2_ = _loc5_;
      var _loc4_;
      while(_loc2_ < process.callArray.length)
      {
         _loc4_ = !process.callArray[_loc2_][2] ? "" : process.callArray[_loc2_][2];
         this.output_txt.text += process.callArray[_loc2_][0] + "    " + process.callArray[_loc2_][1] + "     " + _loc4_ + "\r";
         _loc2_ = _loc2_ + 1;
      }
   }
   function select(obj)
   {
      var _loc4_ = obj.target;
      var _loc3_ = obj.selectedItem;
      var _loc2_;
      if(_loc4_ == this.processList)
      {
         if(_loc3_.toggled)
         {
            _loc2_ = _loc3_.data;
            this.fillSubList(_loc2_.name);
            this.showProcess(_loc2_);
         }
         else
         {
            this.output_txt.text = "";
            this.subProcessList.clearList();
         }
      }
      else if(_loc4_ == this.subProcessList)
      {
         _loc2_ = _loc3_.data;
         this.showProcess(_loc2_);
      }
   }
   function clearList()
   {
      this.output_txt.text = "";
      this.processList.clearList();
      this.subProcessList.clearList();
   }
   function cclength()
   {
      var _loc3_ = 0;
      var _loc2_;
      for(var _loc4_ in lol.server.XMLCCallStack.callList)
      {
         _loc2_ = lol.server.XMLCCallStack.callList[_loc4_];
         _loc3_ += _loc2_.commandList.length;
      }
      this.cc_txt.text = _loc3_;
   }
   function calc()
   {
      this.output_txt.text = "";
      var _loc9_ = Number(this.from_txt.text);
      var _loc10_ = Number(this.to_txt.text);
      var _loc11_ = new Array();
      var _loc7_;
      var _loc8_;
      var _loc6_;
      var _loc5_;
      var _loc4_;
      var _loc2_;
      var _loc3_;
      if(_loc9_ && _loc10_ && _loc10_ >= _loc9_)
      {
         _loc7_ = lol.utils.ExtProfiler.timeArray;
         _loc8_ = Math.floor(_loc9_ / 100);
         _loc6_ = Math.floor(_loc10_ / 100);
         _loc5_ = _loc8_;
         while(_loc5_ <= _loc6_)
         {
            _loc4_ = _loc7_[_loc5_];
            _loc2_ = 0;
            while(_loc2_ < _loc4_.length)
            {
               _loc3_ = _loc4_[_loc2_];
               this.output_txt.text += _loc3_.pname + " " + _loc3_.name + " " + _loc3_.count + "\r";
               _loc2_ = _loc2_ + 1;
            }
            _loc5_ = _loc5_ + 1;
         }
      }
   }
}
