class lol.server.mess.CSM_SSHeap extends lol.server.mess.CSMessage
{
   var _name;
   function CSM_SSHeap(obj, num, target)
   {
      super();
      this._name = "ss_heap_c";
      this.addProp("num",num);
      this.addProp("trg",target);
      this.addProp("obj",obj);
   }
}
